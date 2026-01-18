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
from typing import TypedDict, Optional, List, Dict
from decimal import Decimal, ROUND_DOWN
from notifier import send_telegram_message
from database import Database, VerificationSource, VerificationStatus
from names import names_match


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
    "add_order": "📝 New order added to database as NOT_VERIFIED"
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
     "  ✅The name on ByBit and Wise MUST match to complete the order.\n"
     "  ✅Corporate transfers are accepted.\n\n"
     "Payment details:\n",
    f"💸Account Link:\n {account_link}",
    f"💸Wise Tag:\n {wise_tag}",
    "📩If you have any questions, feel free to contact me on Telegram: @DeFi_Capital📩"
]

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


async def get_wise_balances(wise_client: httpx.AsyncClient, profile_id: str):
    """Get Wise balances with timeout and error handling."""
    try:
        r = await wise_client.get(
            f"{base_url}/v4/profiles/{profile_id}/balances?types=STANDARD",
            timeout=15.0  # Add explicit timeout
        )
        r.raise_for_status()
        return r.json()
    except httpx.TimeoutException:
        print("⚠️ Wise balance request timed out")
        from notifier import send_telegram_message
        send_telegram_message("⚠️ Wise API timeout - balance check failed")
        return []
    except httpx.HTTPError as e:
        print(f"❌ HTTP error getting Wise balances: {e}")
        return []


# ============================================
# RETRY DECORATOR WITH EXPONENTIAL BACKOFF
# ============================================

async def retry_with_backoff(
        func,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 30.0,
        backoff_factor: float = 2.0,
        exceptions=(httpx.HTTPError,)
):
    """
    Retry a coroutine with exponential backoff.

    Args:
        func: Async function to retry
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        backoff_factor: Multiplier for delay on each retry
        exceptions: Tuple of exceptions to catch
    """
    delay = initial_delay

    for attempt in range(max_retries + 1):
        try:
            return await func()
        except exceptions as e:
            if attempt == max_retries:
                # Final attempt failed - re-raise the exception
                raise

            # Calculate next delay with exponential backoff
            wait_time = min(delay, max_delay)
            print(f"⚠️ Attempt {attempt + 1} failed: {e}")
            print(f"   Retrying in {wait_time:.1f} seconds...")

            await asyncio.sleep(wait_time)
            delay *= backoff_factor

    # Should never reach here, but just in case
    raise RuntimeError("Retry logic failed unexpectedly")


# ============================================
# 2. WRAP WISE API CALLS WITH ERROR HANDLING
# ============================================

async def get_incoming_transfers_csv(
        wise_client: httpx.AsyncClient,
        profile_id: str,
        account_id: str,
        currency: str
) -> List[Dict]:
    """
    Fetch CSV statement with proper error handling and retries.
    Returns empty list on failure instead of crashing.
    """
    today = datetime.now(timezone.utc).date()
    start = f"{today}T00:00:00.000Z"
    end = f"{today}T23:59:59.999Z"

    url = (
        f"https://api.wise.com/v3/profiles/{profile_id}/"
        f"borderless-accounts/{account_id}/statement.csv"
        f"?currency={currency}&intervalStart={start}&intervalEnd={end}&type=COMPACT"
    )

    async def fetch():
        response = await wise_client.get(url)
        response.raise_for_status()
        return response.text

    try:
        # Retry the API call with exponential backoff
        csv_text = await retry_with_backoff(
            fetch,
            max_retries=3,
            initial_delay=2.0,
            exceptions=(httpx.HTTPError,)
        )

        # Parse CSV
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

    except httpx.HTTPStatusError as e:
        # HTTP errors (4xx, 5xx)
        print(f"❌ HTTP Error fetching Wise transfers: {e.response.status_code}")
        print(f"   URL: {url}")
        print(f"   Response: {e.response.text[:200]}")  # First 200 chars

        # Send alert but DON'T crash
        from notifier import send_telegram_message
        send_telegram_message(
            f"⚠️ Wise API Error\n"
            f"Status: {e.response.status_code}\n"
            f"Failed to fetch {currency} incoming transfers after 3 retries"
        )
        return []  # Return empty list instead of crashing

    except httpx.RequestError as e:
        # Network errors (connection failed, timeout, etc.)
        print(f"❌ Network Error fetching Wise transfers: {e}")

        from notifier import send_telegram_message
        send_telegram_message(
            f"⚠️ Wise Network Error\n"
            f"Failed to connect to Wise API\n"
            f"Error: {str(e)}"
        )
        return []

    except Exception as e:
        # Unexpected errors
        print(f"❌ Unexpected error in get_incoming_transfers_csv: {e}")

        from notifier import send_telegram_message
        send_telegram_message(
            f"⚠️ Wise Transfer Fetch Error\n"
            f"Unexpected error: {str(e)}"
        )
        return []


async def get_outgoing_transfers_csv(
        wise_client: httpx.AsyncClient,
        profile_id: str,
        account_id: str,
        currency: str
) -> List[Dict]:
    """
    Fetch outgoing transfers with error handling.
    """
    today = datetime.now(timezone.utc).date()
    start = f"{today}T00:00:00.000Z"
    end = f"{today}T23:59:59.999Z"

    url = (
        f"https://api.wise.com/v3/profiles/{profile_id}/"
        f"borderless-accounts/{account_id}/statement.csv"
        f"?currency={currency}&intervalStart={start}&intervalEnd={end}&type=COMPACT"
    )

    async def fetch():
        response = await wise_client.get(url)
        response.raise_for_status()
        return response.text

    try:
        csv_text = await retry_with_backoff(
            fetch,
            max_retries=3,
            initial_delay=2.0,
            exceptions=(httpx.HTTPError,)
        )

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

    except (httpx.HTTPError, Exception) as e:
        print(f"❌ Error fetching outgoing transfers: {e}")

        from notifier import send_telegram_message
        send_telegram_message(
            f"⚠️ Wise Outgoing Transfer Fetch Failed\n"
            f"Error: {str(e)}"
        )
        return []


async def display_balance_and_transactions(wise_client, profile_id, currency="USD"):
    balances = await get_wise_balances(wise_client, profile_id)

    account = None
    for b in balances:
        if b["currency"] == currency:
            account = b
            balance_amount = float(b["amount"]["value"])
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
    # [0] - represents place in a dict. Due to 'coin="USDT"', response contains USDT only
    try:
        current_balance = await client.get_current_balance(
            accountType="FUND",
            coin="USDT"
        )
        present_balance = current_balance["result"]["balance"][0]["transferBalance"]
        return present_balance

    except Exception as e:
        send_telegram_message(f'{alert.get("bybit_balance")} -> {e})')
        raise


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

AD_ONLINE = 10
DEFAULT_TOKEN_ID = "USDT"
DEFAULT_CURRENCY_ID = "USD"
DEFAULT_PAYMENT_IDS = ["21555896"]  # API requires string IDs # Check what it's for
REMARK = ("✅WISE TO WISE ONLY✅\n"
          "💼Payment will be processed via my sole-owned company, IP ZHUCHENKO, LLC\n"
          "⛔- No 3rd party payment accepted\n"
          "✅️Corporate transfers are accepted but subject to verification\n"
          "⚠️If the payment is Pending you must cancel the transfer and the order immediately\n"
          "⚡️🚀Instant release🚀⚡️")

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
"""WARNING! Setting frozen=True makes the instance immutable after creation.
                    Attributes cannot be modified
        Attempts to reassign values raise a FrozenInstanceError"""
@dataclass(frozen=True)
class WiseAdConfig:
    buy_ad_id: str
    sell_ad_id: str

#TODO: Replace with real production buy="1799865939992154112" and sell="1989351720308887552" and more before going live
"""Test ads used"""
TEST_CONFIG = WiseAdConfig(
    buy_ad_id="1977382182365315072",
    sell_ad_id="1975370069588332544",
)


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

#TODO: Think of dynamic price change based on market sentiment
#TODO: Think if you need to split the func() into 3 separate once: data(), buy_logic(), sell_logic()

"""The function itself is bulky but works just fine"""
async def ad_management(client: P2P, wise_balance: float):

    try:
        bybit_balance_result, pending_buys, buy_ad_details, sell_ad_details = await asyncio.gather(
            get_bybit_balance(client),
            fetch_pending_buy_orders(client),
            client.get_ad_details(itemId=TEST_CONFIG.buy_ad_id),
            client.get_ad_details(itemId=TEST_CONFIG.sell_ad_id)
        )

        bybit_balance = float(bybit_balance_result)
        buy_ad_info = buy_ad_details.get("result", {})
        sell_ad_info = sell_ad_details.get("result", {})

        is_buy_active = buy_ad_info.get("status") == AD_ONLINE
        is_sell_active = sell_ad_info.get("status") == AD_ONLINE

    except Exception as e:
        send_telegram_message(f'{alert.get("ad_details")} -> {e})')
        return  # Stop execution if we can't see the ad state

    MIN_THRESHOLD = 500
    MIN_WISE_BALANCE = 500

    locked_funds = 0.0
    if pending_buys:
        for order in pending_buys:
            locked_funds += float(order.get("amount", 0))

    effective_balance = wise_balance - locked_funds - MIN_WISE_BALANCE
    """Remove the line below. It's good for illustration only"""
    print(f"🏦 Wise: ${wise_balance} | 🔒 Locked in Orders: ${locked_funds} | 🟢 Effective: ${effective_balance}")

    ################
    # BUY AD LOGIC #
    ################

    if effective_balance >= MIN_THRESHOLD:
        new_max = str(Decimal(effective_balance).quantize      # new_max is required to be str.
                      (Decimal("0.01"), rounding=ROUND_DOWN))  #Have to preform rounding due to platform limitations

        if is_buy_active:
            action_to_take = ActionType.MODIFY
            log_msg = "Ad is currently active, Modifying ad instead"  # Delete this line. Good for illustration only
        else:
            action_to_take = ActionType.ACTIVATE
            log_msg = "Ad is currently inactive, Activating ad instead"  # Delete this line. Good for illustration only
        print(f"{log_msg} | New max: {new_max}")  # Delete this line. Good for illustration only

        await update_wise_ad(
            client=client,
            ad_id=TEST_CONFIG.buy_ad_id,
            side=AdSide.BUY,
            price=0.97,
            min_amount=150,
            max_amount=5000,
            remark=REMARK,
            action=action_to_take,
            quantity=new_max,
        )

    else:
        print(
            "📉 Effective balance below 500 or active orders exist. Removing Buy Ad.")  # Delete this line. Good for illustration only
        await remove_wise_ad(client=client,
                             ad_id=TEST_CONFIG.buy_ad_id,
                             )

    # TODO: Remove the statement below before going live. It removes test ad so it's not shown on public.
    if effective_balance > 100:
        await remove_wise_ad(
            client=client,
            ad_id=TEST_CONFIG.buy_ad_id
        )
        print("HARD BUY AD REMOVE EXECUTED")

    #################
    # SELL AD LOGIC #
    #################
    effective_bybit_balance = str(bybit_balance) # Required to be a str
    """Sell ad removed IF present balance < 100usdt on ByBit account. Otherwise the ad will remain active"""
    if bybit_balance >= 100:

        if is_sell_active:
            action_to_take = ActionType.MODIFY
            log_msg = "Ad is currently active, Modifying ad instead"  # Delete this line. Good for illustration only
        else:
            action_to_take = ActionType.ACTIVATE
            log_msg = "Ad is currently inactive, Activating ad instead"  # Delete this line. Good for illustration only
        print(f"{log_msg}")  # Delete this line. Good for illustration only

        await update_wise_ad(
            client=client,
            ad_id=TEST_CONFIG.sell_ad_id,
            side=AdSide.SELL,
            price=1.05,
            min_amount=150,
            max_amount=5000,
            remark=REMARK,
            action=action_to_take,
            quantity=effective_bybit_balance
        )
    else:
        await remove_wise_ad(
            client=client,
            ad_id=TEST_CONFIG.sell_ad_id,
        )
        print("SELL AD REMOVED")  # Remove this line before going live. It's good for visualization purpose only

    # TODO: Remove the statement below before going live. It removes test ad so it's not shown on public.
    if bybit_balance > 100:
        await remove_wise_ad(
            client=client,
            ad_id=TEST_CONFIG.sell_ad_id,
        )
        print("HARD SELL AD REMOVE EXECUTED")

# async def qr_upload(client: P2P):
#     qr = "C:/Users/Kirill/Desktop/P2P_API/ByBit/Bybit_P2P_Test/qr.jpg"
#     await client.upload_chat_file(upload_file=qr)




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

"""NEED THIS FUNC ONLY TO FETCH RECIPIENT'S DATA, FOR paymentType PLEASE REFER TO 'get_pending_sell_order_details()'"""
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

"""TO BE REMOVED IN THE FUTURE"""
async def get_chat_message(client: P2P):
    msg = await client.get_chat_messages(
        orderId="2002879935441309696",
        startMessageId=0,
        size=100
    )
    return msg["result"]["result"]


#TODO: Think of adding QR-code. Payment link doesn't work with USD via Wise API calls
# async def send_chat_message(client: P2P):
#     orders = await fetch_pending_sell_orders(client=client)
#
#     if not orders:
#         print("NO PENDING ORDERS FOUND")
#         return
#
#     for order in orders:
#         order_id = order["order_id"]
#         print(f"Sending message to {order_id}")  #see if i need this line of code
#         try:
#             for msg in message:
#                 await client.send_chat_message(
#                     message=msg,
#                     contentType="str",
#                     orderId=order_id,
#                     msgUuid=uuid.uuid4().hex,
#                 )
#                 await asyncio.sleep(0.5)
#             await qr_upload(client=client)
#             print(f"Message sequence sent for {order_id}")
#         except Exception as e:
#             send_telegram_message(f'{alert.get("bybit_msg")} for {order_id} -> {e}')


async def send_payment_instructions(client: P2P, db: Database):
    """
    Send payment instructions to new SELL orders that haven't been messaged yet.
    Uses database to track messaging status - survives bot restarts.

    Features:
    - Automatic retry on failure (up to 3 attempts)
    - Database tracking
    - Detailed logging
    - Error handling
    - Prevents duplicate messages
    """
    sell_orders = await fetch_pending_sell_orders(client=client)

    if not sell_orders:
        return

    print(f"\n📬 Checking {len(sell_orders)} pending SELL orders for messaging...")
    messages_sent = 0

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
                print(f"📝 New order {order_id} added to database")
            except Exception as e:
                print(f"⚠️ Failed to add order {order_id} to database: {e}")
                continue

        # Check if message was already sent
        if db.was_order_messaged(order_id):
            continue  # Skip - already messaged

        # Send payment instructions
        print(f"\n📨 Sending payment instructions to order {order_id}")
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

                # Optional: Upload QR code
                qr_path = "qr.jpg"
                await client.upload_chat_file(upload_file=qr_path, orderId=order_id)

                success = True

            except Exception as e:
                retry_count += 1
                print(f"   ❌ Attempt {retry_count} failed: {e}")

                if retry_count < max_retries:
                    print(f"   🔄 Retrying in 2 seconds...")
                    await asyncio.sleep(2)
                else:
                    print(f"   ⛔ Max retries reached for order {order_id}")
                    send_telegram_message(
                        f'{alert.get("bybit_msg")} for {order_id} after {max_retries} attempts -> {e}'
                    )

        if success:
            # Mark as messaged in database
            db.mark_order_messaged(order_id, retry_count)
            messages_sent += 1
            print(f"   ✅ Payment instructions sent successfully (attempt {retry_count + 1})")

            # Send confirmation to admin (optional - comment out if too noisy)
            send_telegram_message(
                f"📨 Payment instructions sent\n"
                f"Order: {order_id}\n"
                f"Buyer: {buyer_name}\n"
                f"Amount: ${amount}"
            )

    if messages_sent > 0:
        print(f"\n✅ Sent payment instructions to {messages_sent} new order(s)")
    else:
        print(f"✅ No new orders requiring messages")

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
    orders_list = await get_sell_order_id(client=client)

    if not orders_list:
        print("NO PENDING SELL ORDERS FOUND")
        return []

    return await get_order_details_generic(client, orders_list)

"""paymentType is 0 when the order is open. It's getting the correct paymentType (78) whenever its marked as paid"""
async def get_pending_buy_order_details(client: P2P):
    orders_list = await get_buy_order_id(client=client)

    if not orders_list:
        print("NO PENDING BUY ORDERS FOUND")
        return []

    return await get_order_details_generic(client, orders_list)


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
                send_telegram_message(f'{alert.get("add_order")} Order #{order_id}')
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

    print("Chat message:",
          await get_chat_message(client=api)
          )

    # print("Message sent:",
    #       await send_chat_message(client=api)
    #       )

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


    # Use proper timeout and limits for httpx
    timeout = httpx.Timeout(30.0, connect=10.0)
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)

    headers = {
        "Authorization": f"Bearer {os.getenv('API_TOKEN')}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(
            headers=headers,
            timeout=timeout,
            limits=limits
    ) as wise_client:

        # Get Wise profile
        try:
            profiles = await wise_client.get("https://api.wise.com/v2/profiles")
            profiles.raise_for_status()
            profiles_data = profiles.json()
        except Exception as e:
            print(f"❌ Failed to get Wise profiles: {e}")
            return

        business_profile = None
        for p in profiles_data:
            if p["type"] == "BUSINESS":
                business_profile = p
                break

        if not business_profile:
            print("❌ No business profile found")
            return

        profile_id = business_profile["id"]
        print(f"\n👤 Using BUSINESS Profile ID: {profile_id}")
        print("🔍 Starting continuous verification loop...\n")

        last_cleanup = datetime.now()
        consecutive_errors = 0
        max_consecutive_errors = 5

        while True:
            try:
                # Your main logic here
                await send_payment_instructions(api, db)

                current_wise_usd = await get_wise_balance_value(wise_client, profile_id, "USD")
                await ad_management(api, current_wise_usd)

                await display_balance_and_transactions(wise_client, profile_id, "USD")

                await verify_transfer(
                    client=api,
                    wise_client=wise_client,
                    profile_id=profile_id,
                    db=db,
                    currency="USD"
                )

                # Reset error counter on success
                consecutive_errors = 0

            except Exception as e:
                consecutive_errors += 1
                print(f"❌ Error in main loop (attempt {consecutive_errors}/{max_consecutive_errors}): {e}")

                from notifier import send_telegram_message
                send_telegram_message(
                    f"⚠️ Main Loop Error\n"
                    f"Attempt {consecutive_errors}/{max_consecutive_errors}\n"
                    f"Error: {str(e)}"
                )

                if consecutive_errors >= max_consecutive_errors:
                    send_telegram_message(
                        f"🛑 CRITICAL: Main loop failed {max_consecutive_errors} times in a row\n"
                        f"Bot stopping to prevent infinite error loop"
                    )
                    raise  # Stop the bot

                # Wait longer before retrying after an error
                await asyncio.sleep(60)
                continue

            await asyncio.sleep(30)


asyncio.run(main())