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
from typing import TypedDict


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
    """Fetch user profiles."""
    r = await wise_client.get(f"{base_url}/v2/profiles")
    r.raise_for_status()
    return r.json()

async def get_wise_balance_value(wise_client, profile_id, currency="USD") -> float:
    balances = await get_wise_balances(wise_client, profile_id)
    for b in balances:
        if b["currency"] == currency:
            return float(b["amount"]["value"])
    return 0.0

"""Think of removing/refactoring func() below, since it only suitable for representing purposes"""
async def get_wise_balances(wise_client, profile_id):
    """Fetch balances for business account."""
    r = await wise_client.get(f"{base_url}/v4/profiles/{profile_id}/balances?types=STANDARD")
    r.raise_for_status()
    return r.json()

"""Original code:"""
async def get_incoming_transfers_csv(wise_client, profile_id, account_id, currency):
    """Fetch CSV statement for today and extract incoming (CREDIT) transfers."""
    today = datetime.now(timezone.utc).date()  # timezone-aware UTC
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


async def get_outgoing_transfers_csv(wise_client, profile_id, account_id, currency):
    """Fetch CSV statement for today and extract incoming (CREDIT) transfers."""
    today = datetime.now(timezone.utc).date()  # timezone-aware UTC
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
                "time" : row.get("Date Time")
            })

    return outgoing


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
        print(f"❌ No {currency} balance found.")
        return

    incoming_today = await get_incoming_transfers_csv(wise_client, profile_id, account["id"], currency)

    if incoming_today:
        print("📥 Incoming transfers today:")
        for tx in incoming_today:
            print(f"   + {tx['amount']} {currency} | {tx['name']} | Ref: {tx['reference']} | {tx['time']}")
    else:
        print("⚠️ No incoming transfers today.")

    outgoing_today = await get_outgoing_transfers_csv(wise_client, profile_id, account["id"], currency)

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
        print(f"Failed to fetch balance: {e}")
        # TODO: add sending a Telegram msg in case of failure instead of printing error
        # 'raise' will abort current session after sending a telegram msg
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

class OrderSide(IntEnum):
    BUY = 0
    SELL = 1

class ActionType(StrEnum):
    MODIFY = "MODIFY"
    ACTIVATE = "ACTIVE"

STATUS_ONLINE = 10
DEFAULT_TOKEN_ID = "USDT"
DEFAULT_CURRENCY_ID = "USD"
DEFAULT_PAYMENT_IDS = ["21555896"]  # API requires string IDs
#TODO: Add remark
REMARK = "PASS"

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
    remark: REMARK,
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
        "remark": REMARK,
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
#TODO: Adjust price, min/max_amount, etc.
#TODO: Think if you need to split the func() into 3 separate once: data(), buy_logic(), sell_logic()

"""The function itself is bulky but works just fine"""
async def ad_management(client: P2P, wise_balance: float):
    # Fetch all data concurrently
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

        is_buy_active = buy_ad_info.get("status") == STATUS_ONLINE
        is_sell_active = sell_ad_info.get("status") == STATUS_ONLINE

    except Exception as e:
        # TODO: Add Telegram msg in case of failure.
        print(f"⚠️ Failed to fetch ad details or balances: {e}")
        return  # Stop execution if we can't see the ad state

    MIN_THRESHOLD = 500
    MIN_WISE_BALANCE = 500

    # Calculate locked liquidity for BUY orders
    locked_funds = 0.0
    if pending_buys:
        for order in pending_buys:
            locked_funds += float(order.get("amount", 0))

    # Calculate effective liquidity for BUY orders
    effective_balance = wise_balance - locked_funds - MIN_WISE_BALANCE
    """Remove the line below. It's good for illustration only"""
    print(f"🏦 Wise: ${wise_balance} | 🔒 Locked in Orders: ${locked_funds} | 🟢 Effective: ${effective_balance}")

    ################
    # BUY AD LOGIC #
    ################

    if effective_balance >= MIN_THRESHOLD:
        new_max = str(effective_balance) # new_max is required to be str.

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
            max_amount=200,
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
        orderId="1992070819939557376",
        startMessageId=0,
        size=100
    )
    return msg["result"]["result"]


async def send_chat_message(client: P2P):
    orders = await fetch_pending_sell_orders(client=client)

    if not orders:
        print("NO PENDING ORDERS FOUND")
        return

    for order in orders:
        order_id = order["order_id"]
        print(f"Sending message to {order_id}")  #see if i need this line of code
        account_link = "https://wise.com/pay/business/ipzhuchenkollc"
        payment_link = "not available at this time"
        #TODO: HAVE TO ADD Payment QR-code instead of Payment link. Payment link doesn't work with USD via Wise API calls
        try:
            response = await client.send_chat_message(
                message=(f"Hello!\n"
                        f"🤖This order is being processed automatically by our P2P bot — no need to wait for a human response🤖\n\n"
                        f"Please procced with the payment to IP ZHUCHENKO, LLC💼.\n\n"
                        f"❗IMPORTANT❗\n\n"
                        f"  ✅The name on ByBit and Wise MUST match to complete the order.\n"
                        f"  ✅Corporate transfers are accepted.\n\n"
                        f"Payment details (also available under the Pay button):\n"
                        f"  💸Wisetag: @ipzhuchenkollc\n"
                        f"  💸Account link: {account_link}\n"
                        f"  💸Payment link: {payment_link}\n\n"
                        f"📩If you have any questions, feel free to contact me on Telegram: @DeFi_Capital📩"),
                contentType="str",
                orderId=order_id,
                msgUuid=uuid.uuid4().hex,
            )
            print("Response:", response)
        except Exception as e:
            print(f"Failed to send message to order {order_id} -> {e}")
            # TODO: Add sending a Telegram msg in case if the msg hasn't been sent. NO HARD/SOFT STOP REQUIRED.

    print("All messages sent")


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


# --- 1. The New Generic Helper Function ---
async def get_order_details_generic(client: P2P, orders_list: list):
    """
    Takes a list of order dictionaries (containing 'orderId') and fetches
    details for all of them concurrently.
    """
    # Create the tasks
    tasks = []
    for order in orders_list:
        tasks.append(client.get_order_details(orderId=order["orderId"]))

    # Execute all tasks in parallel
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
        result.append({
            "orderId": order["orderId"],
            "paymentType": result_data.get("paymentType"),
            "status": result_data.get("status"),
        })

    return result


# --- 2. The Simplified Specific Functions ---
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


#TODO: Need more work on this one

# async def verify_transfer(client: P2P):
#     status_sell = await get_pending_sell_order_details(client=client)
#     status_buy = await get_pending_buy_order_details(client=client)
#     print("Status sell:", status_sell)
#     print("Status buy:", status_buy)
#     if not status_sell:
#         print("No sell transfer at this moment")
#
#     if not status_buy:
#         print("No buy transfer at this moment")
#
#     sell_tasks_status = []
#     for status in status_sell:
#         sell_tasks_status.append(status_sell[0]['status'])
#     try:
#         status_s = status_sell[0]['status']
#         status_b = status_buy[0]['status']
#         if not status_s:
#             print("No SELL transfer at this moment ('status_s')")
#         if status_s:
#             print(status_s)
#         if not status_b:
#             print("No BUY transfer at this moment ('status_b')")
#         if status_b:
#             print(status_b)
#     except Exception as e:
#         print(f"Testy error: {e}")
#     return []
#     # status_a = status[2]
#     # if status_a == 20:
#     #     print("Time to verify transfer")
#     # elif not status_a == 20:
#     #     print("No transfer at this moment")
#     # return status_a


async def verify_transfer(client: P2P):
    # Fetch the details
    status_sell = await get_pending_sell_order_details(client=client)
    status_buy = await get_pending_buy_order_details(client=client)

    print("Status sell:", status_sell)
    print("Status buy:", status_buy)

    # --- FIX 1 & 2: Iterate instead of indexing ---

    # Handle Sell Orders
    if not status_sell:
        print("No sell transfer at this moment")
    else:
        # Loop through ALL sell orders
        for order in status_sell:
            # Safety check: ensure we didn't get an error packet from the previous function
            if "error" in order:
                print(f"Skipping sell order {order.get('orderId')} due to fetch error.")
                continue

            status_s = order.get('status')
            if status_s:
                print(f"Sell Order {order.get('orderId')} status: {status_s}")

    # Handle Buy Orders
    if not status_buy:
        print("No buy transfer at this moment")
    else:
        # Loop through ALL buy orders
        for order in status_buy:
            if "error" in order:
                print(f"Skipping buy order {order.get('orderId')} due to fetch error.")
                continue

            status_b = order.get('status')
            if status_b:
                print(f"Buy Order {order.get('orderId')} status: {status_b}")

    return []



async def main():
    api = P2P(
        testnet=False,
        api_key=os.getenv("API_KEY"),
        api_secret=os.getenv("API_SECRET"),
    )



    print("Current balance in USDT:",
        await get_bybit_balance(client=api)
          )


    print("Wise buy ad details:",
          await fetch_wise_buy_ad_details(client=api)
          )

    print("Wise sell ad details:",
          await fetch_wise_sell_ad_details(client=api)
          )



    # print("Buy ad active:",
    #       await update_wise_ad(
    #           client=api,
    #           ad_id=TEST_CONFIG.buy_ad_id,
    #           side=AdSide.BUY,
    #           price=0.97,
    #           min_amount=150,
    #           max_amount=200,
    #           remark="Contact @kolya5544 on Telegram once you've paid.",
    #           action=ActionType.ACTIVATE,
    #       )
    #       )
    #
    # print("Sell ad active:",
    #       await update_wise_ad(
    #           client=api,
    #           ad_id=TEST_CONFIG.sell_ad_id,
    #           side=AdSide.SELL,
    #           price=1.05,
    #           min_amount=150,
    #           max_amount=200,
    #           remark="Contact @kolya5544 on Telegram once you've paid.",
    #           action=ActionType.ACTIVATE,
    #       )
    #       )
    #
    #
    # #TODO: add logic if there's an error in displaying an ad
    # print("Modify buy ad: ",
    #       await update_wise_ad(
    #           client=api,
    #           ad_id=TEST_CONFIG.buy_ad_id,
    #           side=AdSide.BUY,
    #           price=0.97,
    #           min_amount=150,
    #           max_amount=200,
    #           remark="Contact @kolya5544 on Telegram once you've paid.",
    #           action=ActionType.MODIFY,
    #       )
    #       )
    #
    # print("Modify sell ad: ",
    #     await update_wise_ad(
    #         client=api,
    #         ad_id=TEST_CONFIG.sell_ad_id,
    #         side=AdSide.SELL,
    #         price=1.05,
    #         min_amount=150,
    #         max_amount=200,
    #         remark="Contact @kolya5544 on Telegram once you've paid.",
    #         action=ActionType.MODIFY,
    #     )
    #       )
    #
    #
    # print("Test buy ad removed:",
    #       await remove_wise_ad(
    #         client=api,
    #         ad_id=TEST_CONFIG.buy_ad_id,
    #       )
    # )
    #
    # print("Test sell ad removed:",
    #       await remove_wise_ad(
    #           client=api,
    #           ad_id=TEST_CONFIG.sell_ad_id,
    #       )
    #       )

    # print(await ad_management(
    #     client=api,
    #     wise_balance=
    #     )
    # )



    # TODO: Once marked as paid: paymentType == 78 AND timestamp (withing 30mins) AND Wise sender name == ByBit AND Wise sender amount == ByBit -> Release funds
    # if paymentType =! 78 -> Telegram text msg
    # if Wise Name =! ByBit -> Telegram text
    # if Wise balance =! ByBit -> Telegram text. !!!! round up to 2 decimals. 111.118 -> 111.12, 111.113 -> 111.11
    # if timestamp withing order creation -> proceed

    # payment_type = await get_pending_sell_order_details(client=api) #get paymentType
    # bybit_name = await fetch_pending_sell_orders(client=api) #get buyerRealName
    # bybit_amount = await fetch_pending_sell_orders(client=api) #get amount
    # #TODO: Think of adding timestamp tracking of a created sell order.
    # payment_type = payment_type[0]["paymentType"]
    # buyerRealName = bybit_name[0]["buyerRealName"]
    # amount = bybit_amount[0]["amount"]
    # if payment_type == 78:
    #     # and buyerRealName == wiseBuyerName and amount == wiseBuyerTransfer
    #     # await release_assets(client=api)
    #     print("Ready to release")
    #
    # elif payment_type != 78:
    #     print("Payment type not recognized")
    #     #TODO: Send telegram msg
    # # elif buyerRealName != wiseBuyerName:
    # #     print("Buyer RealName not recognized")
    # #     #TODO: Send Telegram msg
    # # elif amount != wiseBuyerTransfer:
    # #     print("Amount not recognized")
    # #     #TODO: Send Telegram msg
    # else:
    #     print("Attention required")
    #     #TODO: Send Telegram msg

    print("Fetch last 20 Pending sell orders:",
          await fetch_pending_sell_orders(client=api)
          )

    print("Fetch last 20 Pending buy orders:",
          await fetch_pending_buy_orders(client=api)
          )

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



    async with httpx.AsyncClient(headers=headers, timeout=30) as client:

        profiles = await get_profiles(client)

        business_profile = None
        for p in profiles:
            print(f"Profile: {p['id']} | type={p['type']} | name={p.get('fullName')}")
            if p["type"] == "BUSINESS":
                business_profile = p
                break

        if not business_profile:
            print("❌ No business profile found")
            #TODO: If can't find a business profile -> send a Telegram msg
            raise

        profile_id = business_profile["id"]
        print(f"\n👤 Using BUSINESS Profile ID: {profile_id}")
        print("🔁 Starting continuous Wise balance & incoming transfer tracking every 30 seconds...\n")

        while True:
            try:
                # 1. Get Real Wise Balance
                current_wise_usd = await get_wise_balance_value(client, profile_id, "USD")

                # 2. Run Buy Ad Logic (Using Scenario 3)
                await ad_management(api, current_wise_usd)

                # 4. Display functionality
                await display_balance_and_transactions(client, profile_id, "USD")

                # 5. Check transfers
                await verify_transfer(client=api)

            except Exception as e:
                # TODO: Add Telegram msg in case of failure.
                print(f"CRITICAL LOOP ERROR: {e}")
            await asyncio.sleep(30)
        #
    # await api.close_session()



asyncio.run(main())