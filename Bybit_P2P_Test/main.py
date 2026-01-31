'''cannot use mark_as_paid() with USD on Wise, not sure about Revolut. Should be good with EUR'''

from async_bybit_p2p import P2P
import asyncio
import os
import uuid
from io import StringIO
from datetime import datetime, timezone
import httpx
import csv
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import TypedDict, Dict, List
from decimal import Decimal, ROUND_DOWN
from notifier import send_telegram_message
from database import Database, VerificationSource, VerificationStatus
from names import names_match
from breaker import CircuitBreaker, CircuitBreakerOpenError


#=====================
#   Telegram Alerts
#=====================

alert = {
    "bybit_balance": "⛔ATTENTION⛔ Failed to fetch ByBit Balance. Event loop has stopped.",
    "bybit_msg": "⚠️ATTENTION⚠️ Failed to send ByBit Message. Attention required. Event loop is running.",
    "ad_details": "⚠️ATTENTION⚠️ Failed to fetch ad details. Event loop has stopped.",
    "wise_balance": "⛔ATTENTION⛔ Failed to fetch Wise Balance. Event loop has stopped.",
    "wise_profiles": "⛔ATTENTION⛔ Failed to fetch Wise Profiles. Event loop has stopped.",
    "payment_type": "⚠️ATTENTION⚠️ Payment type not recognized. Attention required.",
    "buyer_name": "⚠️ATTENTION⚠️ Buyer RealName not recognized. Attention required.",
    "amount": "⚠️ATTENTION⚠️ Amount not recognized. Attention required.",
    "unknown":  "⚠️ATTENTION⚠️ Unknown issue! Attention required.",
    "loop_error": "⛔ATTENTION⛔ CRITICAL LOOP ERROR. Event loop has stopped.",
    "ad_payload": "⚠️ATTENTION⚠️ Failed to build ad payload. Attention required.",
    "skip_sell": "⚠️ATTENTION⚠️ Skipping sell order due to fetch error. Order # ",
    "skip_buy": "⚠️ATTENTION⚠️ Skipping buy order due to fetch error. Order # ",
    "save_match": "⚠️ATTENTION⚠️ Failed to save matched names in database for order ",
    "verification": "⚠️ATTENTION⚠️ Manual verification required for order #",
    "verify_reject": "⚠️ATTENTION⚠️ Name added to database with low matching score. Order #",
}

#=====================
#    ByBit Message
#=====================

account_link = "https://wise.com/pay/business/ipzhuchenkollc"
wise_tag = "@ipzhuchenkollc"

message = [
    "Hello!\n"
     "🤖This order is being processed automatically by our P2P bot — no need to wait for a human response🤖\n\n"
     "Please procced with the payment to IP ZHUCHENKO, LLC💼.\n\n"
     "❗IMPORTANT❗\n\n"
     "   ✅The name on ByBit and Wise MUST match to complete the order.\n"
     "   ❗Corporate transfers will be rejected with 5% fee.\n\n"
     "Payment details:\n",
    f"💸Account Link:\n {account_link}",
    f"💸Wise Tag:\n {wise_tag}",
    "📩If you have any questions, feel free to contact me on Telegram: @DeFi_Capital📩"
]

#=====================
#       Breakers
#=====================

# Create circuit breakers for each external service
wise_transfers_breaker = CircuitBreaker(
    max_failures=5,           # Open after 5 failures
    timeout=120.0,            # Wait 2 minutes before retry
    name="Wise Transfers",
    alert_callback=send_telegram_message  # Your existing alert function
)

wise_balance_breaker = CircuitBreaker(
    max_failures=3,
    timeout=60.0,             # Wait 1 minute before retry
    name="Wise Balance",
    alert_callback=send_telegram_message
)

bybit_orders_breaker = CircuitBreaker(
    max_failures=5,
    timeout=90.0,             # Wait 1.5 minutes before retry
    name="ByBit Orders",
    alert_callback=send_telegram_message
)

bybit_balance_breaker = CircuitBreaker(
    max_failures=3,
    timeout=60.0,
    name="ByBit Balance",
    alert_callback=send_telegram_message
)

# Track orders being processed to prevent duplicate handlers (used in send_chat_msg)
active_order_handlers: set[str] = set()

#=====================
#    WISE Cluster
#=====================

api_token = os.getenv("API_TOKEN")
base_url = os.getenv("BASE_URL")

headers = {
    "Authorization": f"Bearer {api_token}",
    "Content-Type": "application/json"
}

async def get_profiles(wise_client):
    r = await wise_client.get(f"{base_url}/v2/profiles")
    r.raise_for_status()
    return r.json()

async def get_wise_balance_value(wise_client, profile_id, currency="USD") -> float:
    balances = await get_wise_balances(wise_client, profile_id)
    for b in balances:
        if b["currency"] == currency:
            return float(b["amount"]["value"])
    return 0.0


async def get_wise_balances(wise_client, profile_id):
    """Fetch balances with circuit breaker protection."""

    async def fetch():
        r = await wise_client.get(f"{base_url}/v4/profiles/{profile_id}/balances?types=STANDARD")
        r.raise_for_status()
        return r.json()

    try:
        return await wise_balance_breaker.call(fetch)
    except (CircuitBreakerOpenError, Exception) as e:
        print(f"⚠️ Failed to get Wise balances: {e}")
        return []


async def get_incoming_transfers_csv(wise_client, profile_id, account_id, currency):
    """
    Fetch incoming transfers with circuit breaker protection.
    Returns empty list if circuit is open or API fails.
    """

    async def fetch():
        today = datetime.now(timezone.utc).date()
        start = f"{today}T00:00:00.000Z"
        end = f"{today}T23:59:59.999Z"

        url = (
            f"{base_url}/v3/profiles/{profile_id}/borderless-accounts/{account_id}/statement.csv"
            f"?currency={currency}&intervalStart={start}&intervalEnd={end}&type=COMPACT"
        )

        response = await wise_client.get(url)
        response.raise_for_status()

        csv_text = response.text
        reader = csv.DictReader(StringIO(csv_text))

        incoming = []
        for row in reader:
            if row.get("Transaction Type") == "CREDIT":
                incoming.append({
                    "amount": float(row.get("Amount", 0)),
                    "name": row.get("Payer Name") or "Unknown",
                    "reference": row.get("TransferWise ID") or "No reference",
                    "time": row.get("Date Time")
                })

        return incoming

    try:
        return await wise_transfers_breaker.call(fetch)
    except (CircuitBreakerOpenError, Exception) as e:
        print(f"⚠️ Failed to get incoming transfers: {e}")
        return []  # Return empty list instead of crashing


async def get_outgoing_transfers_csv(wise_client, profile_id, account_id, currency):
    """Fetch outgoing transfers with circuit breaker protection."""

    async def fetch():
        today = datetime.now(timezone.utc).date()
        start = f"{today}T00:00:00.000Z"
        end = f"{today}T23:59:59.999Z"

        url = (
            f"{base_url}/v3/profiles/{profile_id}/borderless-accounts/{account_id}/statement.csv"
            f"?currency={currency}&intervalStart={start}&intervalEnd={end}&type=COMPACT"
        )

        response = await wise_client.get(url)
        response.raise_for_status()

        csv_text = response.text
        reader = csv.DictReader(StringIO(csv_text))

        outgoing = []
        for row in reader:
            if row.get("Transaction Type") == "DEBIT":
                outgoing.append({
                    "amount": float(row.get("Amount", 0)),
                    "name": row.get("Payee Name") or "Unknown",
                    "reference": row.get("TransferWise ID") or "No reference",
                    "time": row.get("Date Time")
                })

        return outgoing

    try:
        return await wise_transfers_breaker.call(fetch)
    except (CircuitBreakerOpenError, Exception) as e:
        print(f"⚠️ Failed to get outgoing transfers: {e}")
        return []

"""Shadow the function below. It's only good for representation purposes"""
async def display_balance_and_transactions(wise_client, profile_id, currency="USD"):
    balances = await get_wise_balances(wise_client, profile_id)

    account = None
    for b in balances:
        if b["currency"] == currency:
            account = b
            balance_amount = round(float(b["amount"]["value"]), 0)
            print(f"\n[{datetime.now().isoformat()}] 💰 Current {currency} Balance: {balance_amount}")
            break

    if not account:
        """Send tegram alert"""
        print(f"❌ No {currency} balance found.")
        return

    incoming_today = await get_incoming_transfers_csv(wise_client, profile_id, account["id"], currency)
    outgoing_today = await get_outgoing_transfers_csv(wise_client, profile_id, account["id"], currency)

    if incoming_today:
        print("📥 Incoming transfers today:")
        for tx in incoming_today:
            print(f"   + {tx['amount']} {currency} | {tx['name']} | Ref: {tx['reference']} | {tx['time']}")
    else:
        print("⚠️ No incoming transfers today.")

    if outgoing_today:
        print("📥 Outgoing transfers today:")
        for tx in outgoing_today:
            print(f"   {tx['amount']} {currency} | {tx['name']} | Ref: {tx['reference']} | {tx['time']}")
    else:
        print("⚠️ No Outgoing transfers today.")


#=====================
#    ByBit Cluster
#=====================

async def get_bybit_balance(client: P2P):
    """Get ByBit balance with circuit breaker protection."""

    async def fetch():
        current_balance = await client.get_current_balance(
            accountType="FUND",
            coin="USDT"
        )
        return current_balance["result"]["balance"][0]["transferBalance"]

    try:
        return await bybit_balance_breaker.call(fetch)
    except CircuitBreakerOpenError as e:
        print(f"⚠️ ByBit balance check blocked: {e}")
        return "0.0"  # Return safe default
    except Exception as e:
        send_telegram_message(f'{alert.get("bybit_balance")} -> {e})')
        return "0.0"


"""Remove next 2 func below once all set"""
async def fetch_wise_buy_ad_details(client: P2P):
    wise_buy_ad = await client.get_ad_details(itemId="1799865939992154112")
    return wise_buy_ad

async def fetch_wise_sell_ad_details(client: P2P):
    wise_sell_ad = await client.get_ad_details(itemId="1989351720308887552")
    return wise_sell_ad

"""Ad config section"""

# ============================
# ENUMS & CONSTANTS
# ============================

class AdSide(IntEnum):
    BUY = 0
    SELL = 1

class ActionType(StrEnum):
    MODIFY = "MODIFY"
    ACTIVATE = "ACTIVE"

class OrderSide(IntEnum):
    BUY = 0
    SELL = 1

class OrderStatus(IntEnum):
    PENDING = 10
    PAID = 20
    APPEAL = 30

class PaymentType(IntEnum):
    WISE = 78

MY_USER_ID = '124981367'
AD_ONLINE = 10
DEFAULT_TOKEN_ID = "USDT"
DEFAULT_CURRENCY_ID = "USD"
DEFAULT_PAYMENT_IDS = ["21555896"]  # API requires string IDs # Check what it's for

REMARK = ("◆︎ Trade with Confidence with DeFi_Capital. Your reliable, US-regulated trading partner.\n"
          "\n"
          "By placing a trade request, you agree to the terms below:\n"
          "\n"
          "▶ Compliance & Verification\n"
          "\n"
          # "A one-time KYC verification is required for new clients.\n"
          "To comply with US regulations, DeFi_Capital may request additional documentation.\n"
          "Failure to meet compliance requirements may result in transaction rejection. Refunds are processed taking into account the transfer fee.\n"
          "\n"
          "▶ Payment Policy\n"
          "\n"
          "Payments must be made exclusively from a personal account registered in the client's name.\n"
          "⛔ Third-party or corporate transfers are strictly prohibited and will be automatically rejected.\n"
          "\n"
          "▶ Trade Processing\n"
          "\n"
          "Operations run 24/7.\n"
          "Payments are accepted via one of the associated companies."
          "Trades are completed within minutes after confirmation.\n"
          "\n"
          "▶ Official Support\n"
          "\n"
          "Telegram: @DeFi_Capital\n"
          "Support is available 13:00-5:00 UTC.\n"
          "―Communication is conducted only via the official account listed above.")

DEFAULT_TRADING_PREFERENCES = {
    "hasUnPostAd": 0,
    "isKyc": 1,
    "isEmail": 1,
    "isMobile": 1,
    "hasRegisterTime": 0,
    "registerTimeThreshold": 0,
    "orderFinishNumberDay30": 0,
    "completeRateDay30": "",
    "nationalLimit": "",
    "hasOrderFinishNumberDay30": 1,
    "hasCompleteRateDay30": 1,
    "hasNationalLimit": 0,
}


# ============================
# TYPING
# ============================

class AdPayload(TypedDict):
    id: str
    priceType: int
    tokenId: str
    currencyId: str
    side: int
    premium: int
    price: float
    minAmount: int
    maxAmount: int
    remark: str
    tradingPreferenceSet: dict
    paymentIds: list[str]
    actionType: str
    quantity: str
    paymentPeriod: str


# ============================
# CONFIG
# ============================
@dataclass(frozen=True)
class WiseAdConfig:
    buy_ad_id: str
    sell_ad_id_low: str
    sell_ad_id_med: str
    sell_ad_id_high: str

AD_CONFIG = WiseAdConfig(
    buy_ad_id="1977382182365315072",
    sell_ad_id_low="1793255340480356352",
    sell_ad_id_med="1975370069588332544",
    sell_ad_id_high="1793292594570334208",
)

@dataclass
class PriceTier:
    name: str
    ad_id: str
    price: float
    min_price: float
    max_price: float

@dataclass
class MarketPrices:
    bot: float
    mid: float
    top: float

# ============================
# PAYLOAD BUILDER
# ============================

def build_ad_payload(
    *,
    ad_id: str,
    side: AdSide,
    price: float,
    min_amount: int,
    max_amount: int,
    remark: str = REMARK,
    action_type: ActionType,
    quantity: str,
    payment_period: str = "15",
) -> AdPayload:
    if price <= 0:
        raise ValueError("price must be positive")

    if min_amount > max_amount:
        raise ValueError("min_amount cannot exceed max_amount")

    return {
        "id": ad_id,
        "priceType": 0,
        "tokenId": DEFAULT_TOKEN_ID,
        "currencyId": DEFAULT_CURRENCY_ID,
        "side": int(side),
        "premium": 0,
        "price": price,
        "minAmount": min_amount,
        "maxAmount": max_amount,
        "remark": remark,
        "tradingPreferenceSet": DEFAULT_TRADING_PREFERENCES,
        "paymentIds": DEFAULT_PAYMENT_IDS,
        "actionType": action_type,
        "quantity": quantity,
        "paymentPeriod": payment_period,
    }


# ============================
# SINGLE UPDATE ENTRY POINT
# ============================

async def update_wise_ad(
    *,
    client: "P2P",
    ad_id: str,
    side: AdSide,
    price: float,
    min_amount: int,
    max_amount: int,
    remark: str,
    action: ActionType,
    quantity: str
):
    try:
        payload = build_ad_payload(
            ad_id=ad_id,
            side=side,
            price=price,
            min_amount=min_amount,
            max_amount=max_amount,
            remark=remark,
            action_type=action,
            quantity=quantity
        )
        return await client.update_ad(**payload)
    except ValueError as e:
        send_telegram_message(f'{alert.get("ad_payload")} -> {e})')


def remove_ad_payload(
    *,
    ad_id: str,
):
    return {"itemId": ad_id}

async def remove_wise_ad(
        *,
        client: P2P,
        ad_id: str,
):
    payload = remove_ad_payload(
        ad_id=ad_id,
    )
    return await client.remove_ad(**payload)

async def get_market_prices(client: P2P) -> MarketPrices:
    """Fetches and calculates competitive market prices"""
    raw_data = await client.get_online_ads(
        tokenId='USDT',
        currencyId='USD',
        side='1',
        size='1000',
    )

    data = raw_data.get('result', {}).get('items', [])

    # Filter by payment method
    filtered = [
        item for item in data
        if '78' in item.get('payments', [])
    ]

    # Filter by price range and min amount
    filtered = [
        item for item in filtered
        if 1.01 <= float(item.get('price', 0)) <= 1.05
           and float(item.get('minAmount', 0)) >= 200
    ]

    # Categorize by price tier
    low = [item for item in filtered if 1.01 <= float(item['price']) <= 1.02]
    med = [item for item in filtered if 1.017 <= float(item['price']) <= 1.03]
    high = [item for item in filtered if 1.025 <= float(item['price']) <= 1.05]

    # Calculate averages with safety checks
    bot = round(sum(float(i['price']) for i in low) / len(low) - 0.001, 3) if low else 1.02
    mid = round(sum(float(i['price']) for i in med) / len(med) - 0.001, 3) if med else 1.03
    top = round(sum(float(i['price']) for i in high) / len(high), 3) if high else 1.04

    return MarketPrices(bot=bot, mid=mid, top=top)


async def manage_buy_ad(
        client: P2P,
        effective_balance: float,
        is_active: bool,
        buy_price: float = 0.97
):
    """Manages the buy ad based on available balance"""
    MIN_THRESHOLD = 500

    if effective_balance >= MIN_THRESHOLD:
        new_max = str(Decimal(effective_balance).quantize(
            Decimal("0.01"), rounding=ROUND_DOWN
        ))
        if is_active:
            action = ActionType.MODIFY
        else:
            action = ActionType.ACTIVATE
        # action = ActionType.MODIFY if is_active else ActionType.ACTIVATE

        await update_wise_ad(
            client=client,
            ad_id=AD_CONFIG.buy_ad_id,
            side=AdSide.BUY,
            price=buy_price,
            min_amount=200,
            max_amount=5000,
            remark=REMARK,
            action=action,
            quantity=new_max,
        )
    else:
        await remove_wise_ad(client=client, ad_id=AD_CONFIG.buy_ad_id)

    #TODO: Remove if statement below before going live
    if effective_balance > 100:
        await remove_wise_ad(client=client, ad_id=AD_CONFIG.buy_ad_id)
        print("HARD REMOVE BUY AD EXECUTED")


async def manage_sell_ads(
        client: P2P,
        bybit_balance: float,
        market_prices: MarketPrices,
        sell_ads_status: Dict[str, bool]
):
    """Manages all three sell ads with dynamic pricing"""
    tiers = [
        PriceTier("low", AD_CONFIG.sell_ad_id_low, market_prices.bot, 1.01, 1.02),
        PriceTier("med", AD_CONFIG.sell_ad_id_med, market_prices.mid, 1.017, 1.03),
        PriceTier("high", AD_CONFIG.sell_ad_id_high, market_prices.top, 1.025, 1.05),
    ]

    effective_balance = str(bybit_balance)

    if bybit_balance >= 100:
        for tier in tiers:
            clamped_price = max(tier.min_price, min(tier.price, tier.max_price))

            action = (ActionType.MODIFY if sell_ads_status.get(tier.ad_id)
                      else ActionType.ACTIVATE)

            await update_wise_ad(
                client=client,
                ad_id=tier.ad_id,
                side=AdSide.SELL,
                price=clamped_price,
                min_amount=200,
                max_amount=5000,
                remark=REMARK,
                action=action,
                quantity=effective_balance
            )
    else:
        # Remove all sell ads if balance too low
        for tier in tiers:
            await remove_wise_ad(client=client, ad_id=tier.ad_id)


async def ad_management(client: P2P, wise_balance: float):
    try:
        # Fetch all data in parallel
        (bybit_balance_result, pending_buys, buy_ad_details,
         sell_low_ad_details, sell_med_ad_details, sell_high_ad_details,
         market_prices) = await asyncio.gather(
            get_bybit_balance(client),
            fetch_pending_buy_orders(client),
            client.get_ad_details(itemId=AD_CONFIG.buy_ad_id),
            client.get_ad_details(itemId=AD_CONFIG.sell_ad_id_low),
            client.get_ad_details(itemId=AD_CONFIG.sell_ad_id_med),
            client.get_ad_details(itemId=AD_CONFIG.sell_ad_id_high),
            get_market_prices(client),  # Fetch dynamic prices
        )

        bybit_balance = float(bybit_balance_result)

        # Calculate effective balance
        locked_funds = sum(float(o.get("amount", 0)) for o in (pending_buys or []))
        effective_balance = wise_balance - locked_funds - 500

        # Manage buy ad
        is_buy_active = buy_ad_details.get("result", {}).get("status") == AD_ONLINE
        await manage_buy_ad(client, effective_balance, is_buy_active)

        # Manage sell ads with dynamic pricing
        sell_ads_status = {
            AD_CONFIG.sell_ad_id_low: sell_low_ad_details.get("result", {}).get("status") == AD_ONLINE,
            AD_CONFIG.sell_ad_id_med: sell_med_ad_details.get("result", {}).get("status") == AD_ONLINE,
            AD_CONFIG.sell_ad_id_high: sell_high_ad_details.get("result", {}).get("status") == AD_ONLINE,
        }

        await manage_sell_ads(client, bybit_balance, market_prices, sell_ads_status)

    except Exception as e:
        send_telegram_message(f'{alert.get("ad_details")} -> {e}')


async def fetch_pending_sell_orders(client: P2P):
    orders_raw = await client.get_pending_orders(
        side=OrderSide.SELL,
        page=1,
        size=20
    )
    orders = orders_raw["result"]["items"]

    result = []
    for o in orders:
        entry = {
            "order_id": o["id"],
            "name": o["buyerRealName"],
            "amount": o["amount"],
            "createDate": o["createDate"],
        }
        result.append(entry)

    return result


async def fetch_pending_buy_orders(client: P2P):
    orders_raw = await client.get_pending_orders(
        side=OrderSide.BUY,
        page=1,
        size=20
    )
    orders = orders_raw["result"]["items"]


    result = []
    for o in orders:
        entry = {
            "order_id": o["id"],
            "name": o["sellerRealName"],
            "amount": o["amount"],
            "createDate": o["createDate"],
        }
        result.append(entry)

    return result


"""REQUIRES MORE WORK ON THIS ONE"""
async def release_assets(client: P2P):
    action = await client.release_assets()
    return action

#TODO: Remove this func()
async def get_chat_message(client: P2P):
    msg = await client.get_chat_messages(
        orderId="2007879965210968064",
        startMessageId=0,
        size=100
    )
    return msg["result"]["result"]


async def send_payment_instructions_immediate(client: P2P, order_id: str, buyer_name: str, amount: str) -> bool:
    """
    Send payment instructions immediately to a specific order.
    Returns True if successful, False otherwise.

    This is the actual message sending function called by the race condition handler.
    """
    print(f"\n [Order {order_id}]    Sending payment instructions NOW ")
    print(f"   Buyer: {buyer_name} | Amount: ${amount}")

    retry_count = 0
    max_retries = 3
    success = False

    while retry_count < max_retries and not success:
        try:
            # Send each message in sequence
            for msg in message:
                await client.send_chat_message(
                    message=msg,
                    contentType="str",
                    orderId=order_id,
                    msgUuid=uuid.uuid4().hex,
                )
                await asyncio.sleep(0.5)  # Rate limiting

            try:
                qr_path = "C:/Users/Kirill/Desktop/P2P_API/ByBit/Bybit_P2P_Test/qr.jpg"
                file_path = await client.upload_chat_file(upload_file=qr_path, orderId=order_id)

                url = file_path.get("result").get("url")

                await client.send_chat_message(
                    message=url,
                    contentType="pic",
                    orderId=order_id,
                    msgUuid=uuid.uuid4().hex,
                )
                print("msg sent")

            except Exception as e:
                print(f" QR upload failed (non-critical): {e}")
                send_telegram_message(f" QR upload failed (non-critical): {e}")

            success = True

        except Exception as e:
            retry_count += 1
            print(f"  Attempt {retry_count} failed: {e}")

            if retry_count < max_retries:
                print(f" Retrying in 2 seconds...  ")
                await asyncio.sleep(2)
            else:
                print(f"   Max retries reached for order {order_id}")
            send_telegram_message(
            f'{alert.get("bybit_msg")} for {order_id} after {max_retries} attempts -> {e}'
            )

    if success:
        print(f"  Payment instructions sent successfully (attempt {retry_count + 1})")

    return success


async def check_for_new_message(client: P2P, order_id: str) -> bool:
    """
    Poll for new messages from the buyer.
    Returns True when ANY buyer message is detected.
    """
    print(f"[Order {order_id}] 👀 Monitoring chat for buyer messages...")

    # Start with zero baseline - any buyer message counts as "new"
    initial_buyer_count = 0

    # Poll for buyer messages every 3 seconds
    while True:
        await asyncio.sleep(3)

        try:
            current_messages = await client.get_chat_messages(
                orderId=order_id,
                size=100
            )
            messages_list = current_messages.get("result", {}).get("result", [])

            # Filter to only buyer messages
            current_buyer_messages = [
                msg for msg in messages_list
                if msg.get('userId') != MY_USER_ID
                   and msg.get('roleType') == 'user'
            ]
            current_buyer_count = len(current_buyer_messages)

            # Any buyer message detected
            if current_buyer_count > initial_buyer_count:
                latest_buyer_msg = current_buyer_messages[0]
                print(f"[Order {order_id}] 📨 Buyer message detected: {latest_buyer_msg.get('message')}")
                return True

        except asyncio.CancelledError:
            # Task was cancelled (timeout won the race)
            print(f"[Order {order_id}] 🛑 Message monitoring cancelled")
            raise  # Re-raise to properly handle cancellation
        except Exception as e:
            print(f"[Order {order_id}] ⚠️ Error checking messages: {e}")
            send_telegram_message(f"[Order {order_id}] ⚠️ Error checking new messages: {e}")
            # Continue polling even if there's an error


async def wait_for_message(client: P2P, order_id: str) -> str:
    """
    Wait for a buyer message.
    Returns "message" when detected.
    """
    await check_for_new_message(client, order_id)
    return "message"


async def wait_for_timeout(order_id: str, seconds: int = 60) -> str:
    """
    Wait for the specified timeout period.
    Returns "timeout" when timer expires.
    """
    print(f"[Order {order_id}] ⏱️  Starting {seconds}-second timer...")
    await asyncio.sleep(seconds)
    print(f"[Order {order_id}] ⏰ Timer expired!")
    return "timeout"


async def handle_order_logic(client: P2P, db: Database, order_id: str, buyer_name: str, amount: str) -> None:
    """
    Race condition handler for a single order.

    Waits for EITHER:
    - Event A: Buyer sends a chat message
    - Event B: 60-second timer expires

    Whichever happens first triggers send_payment_instructions().
    The other event is cancelled immediately.
    """

    # Idempotency check: Prevent duplicate handlers
    if order_id in active_order_handlers:
        print(f"[Order {order_id}] Handler already running, skipping...")
        return

    # Idempotency check: Already messaged
    if db.was_order_messaged(order_id):
        print(f"[Order {order_id}] ✅ Already messaged (per database), skipping...")
        return

    # Mark as active
    active_order_handlers.add(order_id)

    try:
        print(f"\n[Order {order_id}] Starting race condition handler...")
        print(f"   Buyer: {buyer_name} | Amount: ${amount}")

        # Create two competing tasks
        message_task = asyncio.create_task(wait_for_message(client, order_id))
        timeout_task = asyncio.create_task(wait_for_timeout(order_id, seconds=60))

        # Race condition: Wait for the first task to complete
        done, pending = await asyncio.wait(
            {message_task, timeout_task},
            return_when=asyncio.FIRST_COMPLETED
        )

        # Cancel all pending tasks immediately
        for task in pending:
            task.cancel()
            try:
                await task  # Wait for cancellation to complete
            except asyncio.CancelledError:
                pass  # Expected when cancelling

        # Determine which event won the race
        winner_task = done.pop()
        result = winner_task.result()

        if result == "message":
            print(f"[Order {order_id}] Winner: BUYER MESSAGE (buyer sent a message first)")
        else:
            print(f"[Order {order_id}] Winner: TIMEOUT (60 seconds elapsed)")

        # Send payment instructions (idempotency ensured)
        success = await send_payment_instructions_immediate(client, order_id, buyer_name, amount)

        if success:
            # Mark order as messaged in database
            db.mark_order_messaged(order_id, retry_count=0)
            print(f"[Order {order_id}] Order handling completed!\n ")

    except Exception as e:
        print(f"[Order {order_id}] Error in race condition handler: {e}")
        send_telegram_message(f" Race condition error for order {order_id}: {e}")

    finally:
        # Remove from active handlers
        active_order_handlers.discard(order_id)


async def send_payment_instructions(client: P2P, db: Database):
    """
    Check for new SELL orders and launch race condition handlers.

    This is called in the main loop every 30 seconds.
    For each new order, it launches a background task that:
    1. Waits for buyer message OR 60-second timeout
    2. Sends payment instructions when either condition is met
    """
    sell_orders = await fetch_pending_sell_orders(client=client)

    if not sell_orders:
        return

    print(f" Checking {len(sell_orders)} pending SELL orders for race condition handlers...")
    handlers_launched = 0

    for order in sell_orders:
        order_id = order["order_id"]
        buyer_name = order["name"]
        amount = order["amount"]

        # Check if order exists in database
        existing_order = db.get_match_by_order_id(order_id)

        if not existing_order:
        # New order discovered - add to database
            try:
                db.add_order(
                    order_id=order_id,
                    order_side=OrderSide.SELL,
                    order_amount=float(amount),
                    counterparty_name=buyer_name,
                    verification_status=VerificationStatus.NOT_VERIFIED
                )
                print(f"New order {order_id} added to database")


            except Exception as e:
                print(f" Failed to add order {order_id} to database: {e}")
                send_telegram_message(f" Failed to add order {order_id} to database: {e}")
                continue

        # Check if message was already sent
        if db.was_order_messaged(order_id):
            continue  # Skip - already messaged

        # Check if handler is already running
        if order_id in active_order_handlers:
            continue  # Skip - handler already active

            # Launch background race condition handler (NON-BLOCKING)
        print(f"Launching race condition handler for order {order_id}")
        asyncio.create_task(
            handle_order_logic(
                client=client,
                db=db,
                order_id=order_id,
                buyer_name=buyer_name,
                amount=amount
            )
        )
        handlers_launched += 1


    if handlers_launched > 0:
        print(f"Launched {handlers_launched} race condition handler(s)")
    else:
        print(f"No new orders requiring handlers")


async def get_sell_order_id(client: P2P):

    response = await fetch_pending_sell_orders(client=client)

    result = []
    for order in response:
        entry = {
            "orderId": order["order_id"],
        }

        result.append(entry)

    return result


async def get_buy_order_id(client: P2P):

    response = await fetch_pending_buy_orders(client=client)

    result = []
    for order in response:
        entry = {
            "orderId": order["order_id"],
        }

        result.append(entry)

    return result


async def get_order_details_generic(client: P2P, orders_list: list):
    tasks = []
    for order in orders_list:
        tasks.append(client.get_order_details(orderId=order["orderId"]))

    details = await asyncio.gather(*tasks, return_exceptions=True)

    result = []

    for order, detail in zip(orders_list, details):
        if isinstance(detail, Exception):
            print(f"[ERROR] Failed API call for orderId {order['orderId']}: {detail}")
            result.append({
                "orderId": order["orderId"],
                "error": str(detail)
            })
            continue

        result_data = detail.get("result", {})

        side = result_data.get("side")

        order_dict = {
            "orderId": order["orderId"],
            "paymentType": result_data.get("paymentType"),
            "status": result_data.get("status"),
            "createDate": result_data.get("createDate"),
            "amount": result_data.get("amount"),
        }

        if side == OrderSide.BUY:
            order_dict["sellerRealName"] = result_data.get("sellerRealName")
        elif side == OrderSide.SELL:
            order_dict["buyerRealName"] = result_data.get("buyerRealName")

        result.append(order_dict)

    return result



"""paymentType is 0 when the order is open. It's getting the correct paymentType (78) whenever its marked as paid"""
async def get_pending_sell_order_details(client: P2P):
    """Get sell order details with circuit breaker protection."""

    async def fetch():
        orders_list = await get_sell_order_id(client=client)
        if not orders_list:
            print("NO PENDING SELL ORDERS FOUND")
            return []
        return await get_order_details_generic(client, orders_list)

    try:
        return await bybit_orders_breaker.call(fetch)
    except (CircuitBreakerOpenError, Exception) as e:
        print(f"⚠️ Failed to get sell orders: {e}")
        return []

"""paymentType is 0 when the order is open. It's getting the correct paymentType (78) whenever its marked as paid"""
async def get_pending_buy_order_details(client: P2P):
    """Get buy order details with circuit breaker protection."""

    async def fetch():
        orders_list = await get_buy_order_id(client=client)
        if not orders_list:
            print("NO PENDING BUY ORDERS FOUND")
            return []
        return await get_order_details_generic(client, orders_list)

    try:
        return await bybit_orders_breaker.call(fetch)
    except (CircuitBreakerOpenError, Exception) as e:
        print(f"⚠️ Failed to get buy orders: {e}")
        return []


async def verify_transfer(client: P2P, wise_client, profile_id: str, db: Database, currency: str = "USD") -> None:
    """
    Verify transfers between Wise and ByBit orders.
    Only processes orders with status 20 (PAID).
    Uses database to track matched transfers and prevent double-matching.
    """

    # Fetch all necessary data
    sell_orders = await get_pending_sell_order_details(client=client)
    buy_orders = await get_pending_buy_order_details(client=client)

    # Get Wise balance and account ID for transfers
    if sell_orders or buy_orders:
        balances = await get_wise_balances(wise_client, profile_id)
        account = None
        for b in balances:
            if b["currency"] == currency:
                account = b
                break

        if not account:
            print(f"❌ No {currency} balance found on Wise")
            return

        # Fetch incoming and outgoing transfers from Wise
        incoming_transfers = await get_incoming_transfers_csv(
            wise_client, profile_id, account["id"], currency
        )
        outgoing_transfers = await get_outgoing_transfers_csv(
            wise_client, profile_id, account["id"], currency
        )

        print("\n" + "=" * 60)
        print("TRANSFER VERIFICATION STARTING")
        print("=" * 60)

        # Process SELL orders (we expect incoming payments to Wise)
        _process_sell_orders(sell_orders, incoming_transfers, db)

        # Process BUY orders (we expect outgoing payments from Wise)
        _process_buy_orders(buy_orders, outgoing_transfers, db)

        print("=" * 60)
        print("TRANSFER VERIFICATION COMPLETE")
        print("=" * 60 + "\n")
    else:
        print("NO ORDERS TO VERIFY")


def _process_sell_orders(sell_orders: list, incoming_transfers: list, db: Database) -> None:
    """
    Process SELL orders - verify incoming Wise payments from buyers.
    Only verifies orders with status 20 (PAID).
    Uses database to prevent duplicate matching and notifications.
    """

    if not sell_orders:
        print("📊 No pending SELL orders to verify")
        return

    print("\n🔍 VERIFYING SELL ORDERS (Incoming Wise Payments)")
    print("-" * 60)

    for order in sell_orders:
        if "error" in order:
            order_id = order.get('orderId', 'unknown')
            send_telegram_message(f'{alert.get("skip_sell")}{order_id}')
            print(f"⚠️ Skipping SELL order {order_id} due to fetch error")
            continue

        order_id = order.get('orderId')
        status = order.get('status')
        buyer_name = order.get('buyerRealName')
        payment_type = order.get('paymentType')
        create_date = order.get('createDate')
        amount = float(order.get('amount', 0))

        print(f"\n📋 Order ID: {order_id}")
        print(f"   Status: {status} | Buyer: {buyer_name}")
        print(f"   Payment Type: {payment_type} | Amount: ${amount}")

        # Check if order already exists in database
        existing_order = db.get_match_by_order_id(order_id)

        if existing_order:
            # Order exists in database
            if existing_order['verification_status'] == VerificationStatus.VERIFIED:
                print(f"   ✅ Order already verified in database (skipping)")
                continue
            elif existing_order['verification_status'] == VerificationStatus.FRAUD_DETECTED:
                print(f"   🚨 Order previously marked as FRAUD - rechecking for legitimate payment...")
                # Don't skip - continue to check if a real payment has arrived
            else:
                print(f"   📝 Order exists as NOT_VERIFIED, checking for match...")
        else:
            # New order - add to database as NOT_VERIFIED
            try:
                db.add_order(
                    order_id=order_id,
                    order_side=OrderSide.SELL,
                    order_amount=amount,
                    counterparty_name=buyer_name,
                    verification_status=VerificationStatus.NOT_VERIFIED
                )
            except Exception as e:
                print(f"   ⚠️ Failed to add order to database: {e}")

        # Only verify if status is PAID (20)
        if status != OrderStatus.PAID:
            print(f"   ⏳ Order {order_id} not marked as PAID yet (status: {status}). Skipping verification.")
            continue

        # Search for matching transfer in Wise incoming transfers
        matching_transfer = None
        for transfer in incoming_transfers:
            if payment_type == PaymentType.WISE:
                transfer_ref = transfer['reference']

                # Check database if this transfer was already used
                if db.is_transfer_used(transfer_ref):
                    continue

                transfer_amount = float(transfer['amount'])
                transfer_name = transfer['name']

                # Match by amount and name (with some tolerance for amount)
                amount_match = abs(transfer_amount - amount) < 0.01
                # name_match = buyer_name and buyer_name.lower() in transfer_name.lower()

                name_match, match_score = names_match(transfer_name, buyer_name)

                if amount_match and name_match:
                    if match_score >= 0.95:
                        matching_transfer = transfer
                        send_telegram_message(
                            f"{alert.get('verification')} {order_id} with match score {match_score:.2%}.")
                        break
                    elif match_score >= 0.8:
                        matching_transfer = transfer
                        send_telegram_message(
                            f"{alert.get('verification')} {order_id} with match score {match_score:.2%}.")
                        break
                    elif match_score < 0.8:
                        matching_transfer = transfer
                        send_telegram_message(
                            f"{alert.get('verify_reject')} {order_id} with match score {match_score:.2%}.")
                        break

        if matching_transfer:
            print(f"   ✅ VERIFIED: Transfer found on Wise")
            print(f"      Wise Payer: {matching_transfer['name']}")
            print(f"      Wise Amount: ${matching_transfer['amount']}")
            print(f"      Wise Reference: {matching_transfer['reference']}")
            print(f"      Wise Time: {matching_transfer['time']}")

            # Update order to VERIFIED status
            try:
                was_fraud = existing_order and existing_order['verification_status'] == VerificationStatus.FRAUD_DETECTED

                if existing_order:
                    # Check if this was previously marked as fraud
                    if was_fraud:
                        # Override fraud status with verification
                        db.override_fraud_and_verify(
                            order_id=order_id,
                            wise_transfer_reference=matching_transfer['reference'],
                            wise_amount=float(matching_transfer['amount']),
                            wise_direction="CREDIT",
                            verification_source=VerificationSource.WISE_INCOMING
                        )
                        print(f"      ✅ FRAUD STATUS OVERRIDDEN - Order now VERIFIED")
                    else:
                        # Update existing order normally
                        db.update_order_verification(
                            order_id=order_id,
                            wise_transfer_reference=matching_transfer['reference'],
                            wise_amount=float(matching_transfer['amount']),
                            wise_direction="CREDIT",
                            verification_source=VerificationSource.WISE_INCOMING
                        )
                        print(f"      💾 Order updated to VERIFIED in database")
                else:
                    # Add as verified match (shouldn't happen but handle it)
                    match_id = db.add_match(
                        order_id=order_id,
                        order_side=OrderSide.SELL,
                        order_amount=amount,
                        counterparty_name=buyer_name,
                        wise_transfer_reference=matching_transfer['reference'],
                        wise_amount=float(matching_transfer['amount']),
                        wise_direction="CREDIT",
                        verification_source=VerificationSource.WISE_INCOMING
                    )
                    print(f"      💾 Match saved to database (ID: {match_id})")

                print(f"   🚀 Ready to release crypto to buyer")

                # Send success notification
                if not existing_order or existing_order['verification_status'] != VerificationStatus.VERIFIED:
                    if was_fraud:
                        # Special notification for fraud override
                        send_telegram_message(
                            f"✅ FRAUD ALERT RESOLVED - Order {order_id} NOW VERIFIED\n"
                            f"Amount: ${amount}\n"
                            f"Buyer: {buyer_name}\n"
                            f"Wise Transfer: {matching_transfer['reference']}\n"
                            f"Legitimate payment received. Safe to release crypto!"
                        )
                    else:
                        # Normal success notification
                        send_telegram_message(
                            f"✅ SELL Order {order_id} VERIFIED\n"
                            f"Amount: ${amount}\n"
                            f"Buyer: {buyer_name}\n"
                            f"Wise Transfer: {matching_transfer['reference']}\n"
                            f"Ready to release crypto!"
                        )

            except Exception as e:
                print(f"      ⚠️ Failed to save verification to database: {e}")
                send_telegram_message(f"{alert.get("save_match")} {order_id}: {e}")
        else:
            print(f"   ❌ NO MATCH: No corresponding Wise transfer found")
            print(f"      Expected: ${amount} from {buyer_name}")

            # Check if there are any transfers with matching amount but already used
            potential_duplicates = []
            for t in incoming_transfers:
                if abs(float(t['amount']) - amount) < 0.01 and db.is_transfer_used(t['reference']):
                    # Get the order this was matched to
                    existing_match = db.get_match_by_wise_reference(t['reference'])
                    if existing_match:
                        used_by_order = existing_match['order_id']
                        potential_duplicates.append((t, used_by_order))

            if potential_duplicates:
                print(f"   ⚠️ WARNING: Found transfer(s) with matching amount but already matched to other orders")
                for dup_transfer, used_by in potential_duplicates:
                    print(f"      Transfer {dup_transfer['reference']} already used by order {used_by}")
                print(f"      This could be a duplicate fraudulent order!")

                # Mark order as fraud and send alert ONLY if not already marked as fraud
                if not existing_order or existing_order['verification_status'] != VerificationStatus.FRAUD_DETECTED:
                    # Mark as fraud in database
                    try:
                        if existing_order:
                            db.mark_order_as_fraud(order_id)
                            print(f"      🚨 Order marked as FRAUD in database")
                        else:
                            # Add as fraud if doesn't exist
                            db.add_order(
                                order_id=order_id,
                                order_side=OrderSide.SELL,
                                order_amount=amount,
                                counterparty_name=buyer_name,
                                verification_status=VerificationStatus.FRAUD_DETECTED
                            )
                            print(f"      🚨 Order added to database as FRAUD")
                    except Exception as e:
                        print(f"      ⚠️ Failed to mark as fraud: {e}")

                    # Send fraud alert (only once)
                    send_telegram_message(
                        f"🚨 POTENTIAL FRAUD ALERT 🚨\n"
                        f"SELL Order {order_id} marked PAID\n"
                        f"Amount: ${amount} | Buyer: {buyer_name}\n"
                        f"Matching Wise transfer already used for order {potential_duplicates[0][1]}!\n"
                        f"Possible duplicate order scam attempt."
                    )
            else:
                # Send "no match found" alert ONLY if this is a new detection
                if not existing_order or existing_order['verification_status'] == VerificationStatus.NOT_VERIFIED:
                    send_telegram_message(
                        f"⚠️ SELL Order {order_id} marked PAID but no Wise transfer found!\n"
                        f"Expected: ${amount} from {buyer_name}"
                    )


def _process_buy_orders(buy_orders: list, outgoing_transfers: list, db: Database) -> None:
    """
    Process BUY orders - verify outgoing Wise payments to sellers.
    Only verifies orders with status 20 (PAID).
    Uses database to prevent duplicate matching and notifications.
    """

    if not buy_orders:
        print("\n📊 No pending BUY orders to verify")
        return

    print("\n🔍 VERIFYING BUY ORDERS (Outgoing Wise Payments)")
    print("-" * 60)

    for order in buy_orders:
        if "error" in order:
            order_id = order.get('orderId', 'unknown')
            send_telegram_message(f'{alert.get("skip_buy")}{order_id}')
            print(f"⚠️ Skipping BUY order {order_id} due to fetch error")
            continue

        order_id = order.get('orderId')
        status = order.get('status')
        seller_name = order.get('sellerRealName')
        payment_type = order.get('paymentType')
        create_date = order.get('createDate')
        amount = float(order.get('amount', 0))

        print(f"\n📋 Order ID: {order_id}")
        print(f"   Status: {status} | Seller: {seller_name}")
        print(f"   Payment Type: {payment_type} | Amount: ${amount}")

        # Check if order already exists in database
        existing_order = db.get_match_by_order_id(order_id)

        if existing_order:
            # Order exists in database
            if existing_order['verification_status'] == VerificationStatus.VERIFIED:
                print(f"   ✅ Order already verified in database (skipping)")
                continue
            elif existing_order['verification_status'] == VerificationStatus.FRAUD_DETECTED:
                print(f"   🚨 Order previously marked as FRAUD - rechecking for legitimate payment...")
                # Don't skip - continue to check if a real payment has arrived
            else:
                print(f"   📝 Order exists as NOT_VERIFIED, checking for match...")
        else:
            # New order - add to database as NOT_VERIFIED
            try:
                db.add_order(
                    order_id=order_id,
                    order_side=OrderSide.BUY,
                    order_amount=amount,
                    counterparty_name=seller_name,
                    verification_status=VerificationStatus.NOT_VERIFIED
                )
                print(f"   📝 New order added to database as NOT_VERIFIED")
            except Exception as e:
                print(f"   ⚠️ Failed to add order to database: {e}")

        # Only verify if status is PAID (20)
        if status != OrderStatus.PAID:
            print(f"   ⏳ Order {order_id} not marked as PAID yet (status: {status}). Skipping verification.")
            continue

        # Search for matching transfer in Wise outgoing transfers
        matching_transfer = None
        match_score = 0

        for transfer in outgoing_transfers:
            if payment_type == PaymentType.WISE:
                transfer_ref = transfer['reference']

                # Check database if this transfer was already used
                if db.is_transfer_used(transfer_ref):
                    continue

                transfer_amount = abs(float(transfer['amount']))  # Outgoing amounts are negative
                transfer_name = transfer['name']

                # Match by amount and name (with some tolerance for amount)
                amount_match = abs(transfer_amount - amount) < 0.01
                # name_match = seller_name and seller_name.lower() in transfer_name.lower()
                name_match, match_score = names_match(transfer_name, seller_name)

                if amount_match and name_match:
                    if match_score >= 0.95:
                        matching_transfer = transfer
                        send_telegram_message(f"{alert.get('verification')} {order_id} with match score {match_score:.2%}.")
                        break
                    elif match_score >= 0.8:
                        matching_transfer = transfer
                        send_telegram_message(f"{alert.get('verification')} {order_id} with match score {match_score:.2%}.")
                        break
                    else:
                        matching_transfer = transfer
                        send_telegram_message(f"{alert.get('verify_reject')} {order_id} with match score {match_score:.2%}.")
                        break

        if matching_transfer:
            print(f"   ✅ VERIFIED: Payment sent via Wise")
            print(f"      Wise Payee: {matching_transfer['name']}")
            print(f"      Wise Amount: ${abs(float(matching_transfer['amount']))}")
            print(f"      Wise Reference: {matching_transfer['reference']}")
            print(f"      Wise Time: {matching_transfer['time']}")

            # Update order to VERIFIED status
            try:
                was_fraud = existing_order and existing_order['verification_status'] == VerificationStatus.FRAUD_DETECTED

                if existing_order:
                    # Check if this was previously marked as fraud
                    if was_fraud:
                        # Override fraud status with verification
                        db.override_fraud_and_verify(
                            order_id=order_id,
                            wise_transfer_reference=matching_transfer['reference'],
                            wise_amount=abs(float(matching_transfer['amount'])),
                            wise_direction="DEBIT",
                            verification_source=VerificationSource.WISE_OUTGOING
                        )
                        print(f"      ✅ FRAUD STATUS OVERRIDDEN - Order now VERIFIED")
                    else:
                        # Update existing order normally
                        db.update_order_verification(
                            order_id=order_id,
                            wise_transfer_reference=matching_transfer['reference'],
                            wise_amount=abs(float(matching_transfer['amount'])),
                            wise_direction="DEBIT",
                            verification_source=VerificationSource.WISE_OUTGOING
                        )
                        print(f"      💾 Order updated to VERIFIED in database")
                else:
                    # Add as verified match (shouldn't happen but handle it)
                    match_id = db.add_match(
                        order_id=order_id,
                        order_side=OrderSide.BUY,
                        order_amount=amount,
                        counterparty_name=seller_name,
                        wise_transfer_reference=matching_transfer['reference'],
                        wise_amount=abs(float(matching_transfer['amount'])),
                        wise_direction="DEBIT",
                        verification_source=VerificationSource.WISE_OUTGOING
                    )
                    print(f"      💾 Match saved to database (ID: {match_id})")

                print(f"   ✓ Payment confirmed to seller")

                # Send success notification
                if not existing_order or existing_order['verification_status'] != VerificationStatus.VERIFIED:
                    if was_fraud:
                        # Special notification for fraud override
                        send_telegram_message(
                            f"✅ FRAUD ALERT RESOLVED - Order {order_id} NOW VERIFIED\n"
                            f"Amount: ${amount}\n"
                            f"Seller: {seller_name}\n"
                            f"Wise Transfer: {matching_transfer['reference']}\n"
                            f"Legitimate payment confirmed!"
                        )
                    else:
                        # Normal success notification
                        send_telegram_message(
                            f"✅ BUY Order {order_id} VERIFIED\n"
                            f"Amount: ${amount}\n"
                            f"Seller: {seller_name}\n"
                            f"Wise Transfer: {matching_transfer['reference']}\n"
                            f"Payment confirmed!"
                        )

            except Exception as e:
                print(f"      ⚠️ Failed to save verification to database: {e}")
                send_telegram_message(f"{alert.get("save_match")} {order_id}: {e}")
        else:
            print(f"   ❌ NO MATCH: No corresponding Wise payment found")
            print(f"      Expected: ${amount} to {seller_name}")

            # Check if there are any transfers with matching amount but already used
            potential_duplicates = []
            for t in outgoing_transfers:
                if abs(abs(float(t['amount'])) - amount) < 0.01 and db.is_transfer_used(t['reference']):
                    existing_match = db.get_match_by_wise_reference(t['reference'])
                    if existing_match:
                        used_by_order = existing_match['order_id']
                        potential_duplicates.append((t, used_by_order))

            if potential_duplicates:
                print(f"   ⚠️ WARNING: Found transfer(s) with matching amount but already matched to other orders")
                print(f"      This could be a duplicate fraudulent order!")

                # Mark order as fraud and send alert ONLY if not already marked as fraud
                if not existing_order or existing_order['verification_status'] != VerificationStatus.FRAUD_DETECTED:
                    # Mark as fraud in database
                    try:
                        if existing_order:
                            db.mark_order_as_fraud(order_id)
                            print(f"      🚨 Order marked as FRAUD in database")
                        else:
                            # Add as fraud if doesn't exist
                            db.add_order(
                                order_id=order_id,
                                order_side=OrderSide.BUY,
                                order_amount=amount,
                                counterparty_name=seller_name,
                                verification_status=VerificationStatus.FRAUD_DETECTED
                            )
                            print(f"      🚨 Order added to database as FRAUD")
                    except Exception as e:
                        print(f"      ⚠️ Failed to mark as fraud: {e}")

                    # Send fraud alert (only once)
                    send_telegram_message(
                        f"🚨 POTENTIAL FRAUD ALERT 🚨\n"
                        f"BUY Order {order_id} marked PAID\n"
                        f"Amount: ${amount} | Seller: {seller_name}\n"
                        f"Matching Wise payment already used for another order!\n"
                        f"Possible duplicate order scam attempt."
                    )
            else:
                # Send "no match found" alert ONLY if this is a new detection
                if not existing_order or existing_order['verification_status'] == VerificationStatus.NOT_VERIFIED:
                    send_telegram_message(
                        f"⚠️ BUY Order {order_id} marked PAID but no Wise payment found!\n"
                        f"Expected: ${amount} to {seller_name}"
                    )


# Update the main loop to include database
async def main():
    api = P2P(
        testnet=False,
        api_key=os.getenv("API_KEY"),
        api_secret=os.getenv("API_SECRET"),
    )

    # Initialize database
    db = Database()
    print("✅ Database initialized")

    print("Current balance in USDT:",
        await get_bybit_balance(client=api)
          )


    print("Wise buy ad details:",
          await fetch_wise_buy_ad_details(client=api)
          )

    print("Wise sell ad details:",
          await fetch_wise_sell_ad_details(client=api)
          )

    print("Fetch last 20 Pending sell orders:",
          await fetch_pending_sell_orders(client=api)
          )

    print("Fetch last 20 Pending buy orders:",
          await fetch_pending_buy_orders(client=api)
          )

    # print(await api.qr_upload(client=api, upload_file="C:/Users/Kirill/Desktop/P2P_API/ByBit/Bybit_P2P_Test/qr.jpg", orderId='2002879935441309696'))

    # print(await qr_upload(client=api))

    print("Chat message before:",
          await get_chat_message(client=api)
          )


    """NEED to fix this!"""
    print("Sell order Info:",
          await get_pending_sell_order_details(client=api)
          )

    print("Buy order Info:",
          await get_pending_buy_order_details(client=api)
          )


    """NEED to fix this!"""

    print("Test order details", await api.get_order_details(
        # orderId="1993151227714883584"
        orderId = "2002879935441309696"
    ))

    # 8. Get Pending Orders
    print("Pending orders:", await api.get_pending_orders(
        side=0,
        page=1,
        size=10,
    )
          )

    # 9. Get counterparty info
    print("get info:", await api.get_counterparty_info(
        originalUid="177871751",
        orderId="1992070819939557376"
    ))

    # Add timeout and connection limits to prevent resource leaks
    timeout = httpx.Timeout(30.0, connect=10.0)
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)

    async with httpx.AsyncClient(headers=headers, timeout=timeout, limits=limits) as wise_client:

        profiles = await get_profiles(wise_client)

        business_profile = None
        for p in profiles:
            print(f"Profile: {p['id']} | type={p['type']} | name={p.get('fullName')}")
            if p["type"] == "BUSINESS":
                business_profile = p
                break

        if not business_profile:
            print("❌ No business profile found")
            send_telegram_message(alert.get("wise_profiles"))
            raise

        profile_id = business_profile["id"]
        print(f"\n👤 Using BUSINESS Profile ID: {profile_id}")
        print("🔍 Starting continuous verification loop...\n")

        last_cleanup = datetime.now()
        consecutive_errors = 0
        max_consecutive_errors = 5

        while True:
            try:

                await send_payment_instructions(api, db)

                current_wise_usd = await get_wise_balance_value(wise_client, profile_id, "USD")
                await ad_management(api, current_wise_usd)

                """Good for representation only, no need to keep it"""
                await display_balance_and_transactions(wise_client, profile_id, "USD")

                await verify_transfer(
                    client=api,
                    wise_client=wise_client,
                    profile_id=profile_id,
                    db=db,
                    currency="USD"
                )

                # Display database statistics
                stats = db.get_statistics()
                print(f"\n📊 Database Stats: {stats['total_matches']} total | "
                      f"{stats['verified_orders']} verified | {stats['unverified_orders']} unverified | "
                      f"{stats['fraud_orders']} fraud")
                print(f"   Buy: ${stats['total_buy_volume']:.2f} | Sell: ${stats['total_sell_volume']:.2f}")

                # Daily cleanup
                if (datetime.now() - last_cleanup).days >= 1:
                    print("\n🗑️ Running daily cleanup...")

                    unverified_count = len(db.get_unverified_orders())
                    if unverified_count > 0:
                        deleted = db.delete_unverified_orders()
                        print(f"   🗑️ Deleted {deleted} unverified orders")

                    old_count = db.get_old_matches_count(days=30)
                    if old_count > 0:
                        archived = db.archive_old_matches(days=30)
                        print(f"   📦 Archived {archived} old verified orders")

                    last_cleanup = datetime.now()

                # Reset error counter on successful iteration
                consecutive_errors = 0

            except Exception as e:
                consecutive_errors += 1
                print(f"\n❌ Error in main loop (attempt {consecutive_errors}/{max_consecutive_errors})")
                print(f"   Error: {e}")

                send_telegram_message(
                    f"⚠️ Main Loop Error (attempt {consecutive_errors}/{max_consecutive_errors})\n"
                    f"Error: {str(e)}"
                )

                if consecutive_errors >= max_consecutive_errors:
                    send_telegram_message(
                        f"🛑 CRITICAL ERROR\n"
                        f"Main loop failed {max_consecutive_errors} times consecutively\n"
                        f"Bot stopping to prevent infinite error loop"
                    )
                    raise

                # Wait longer after error
                print(f"⏳ Waiting 60 seconds before retry...\n")
                await asyncio.sleep(60)
                continue

            # Normal delay between iterations
            await asyncio.sleep(30)


asyncio.run(main())