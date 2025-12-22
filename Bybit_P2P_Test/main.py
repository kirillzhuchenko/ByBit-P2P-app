'''cannot use mark_as_paid() with USD on Wise, not sure about Revolut. Should be good with EUR'''

"""Removed func():
fetch_test_ad_details(), fetch_ads_list(), fetch_wise_buy_ad(), fetch_wise_sell_ad(), fetch_list_of_sell_orders(),
fetch_bybit_counterparty_info()"""


from async_bybit_p2p import P2P
import asyncio
import os
import uuid
from io import StringIO
from datetime import datetime, timezone
import httpx
import csv


#=====================
#    WISE Cluster
#=====================

api_token = os.getenv("API_TOKEN")
base_url = os.getenv("BASE_URL")

headers = {
    "Authorization": f"Bearer {api_token}",
    "Content-Type": "application/json"
}

async def get_profiles(client):
    """Fetch user profiles."""
    r = await client.get(f"{base_url}/v2/profiles")
    r.raise_for_status()
    return r.json()


async def get_wise_balances(client, profile_id):
    """Fetch balances for business account."""
    r = await client.get(f"{base_url}/v4/profiles/{profile_id}/balances?types=STANDARD")
    r.raise_for_status()
    return r.json()

"""Original code:"""
async def get_incoming_transfers_csv(client, profile_id, account_id, currency):
    """Fetch CSV statement for today and extract incoming (CREDIT) transfers."""
    today = datetime.now(timezone.utc).date()  # timezone-aware UTC
    start = f"{today}T00:00:00.000Z"
    end = f"{today}T23:59:59.999Z"

    url = (
        f"{base_url}/v3/profiles/{profile_id}/borderless-accounts/{account_id}/statement.csv"
        f"?currency={currency}&intervalStart={start}&intervalEnd={end}&type=COMPACT"
    )

    response = await client.get(url)
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


async def get_outgoing_transfers_csv(client, profile_id, account_id, currency):
    """Fetch CSV statement for today and extract incoming (CREDIT) transfers."""
    today = datetime.now(timezone.utc).date()  # timezone-aware UTC
    start = f"{today}T00:00:00.000Z"
    end = f"{today}T23:59:59.999Z"

    url = (
        f"{base_url}/v3/profiles/{profile_id}/borderless-accounts/{account_id}/statement.csv"
        f"?currency={currency}&intervalStart={start}&intervalEnd={end}&type=COMPACT"
    )

    response = await client.get(url)
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


async def display_balance_and_transactions(client, profile_id, currency="USD"):
    balances = await get_wise_balances(client, profile_id)

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

    incoming_today = await get_incoming_transfers_csv(client, profile_id, account["id"], currency)

    if incoming_today:
        print("📥 Incoming transfers today:")
        for tx in incoming_today:
            print(f"   + {tx['amount']} {currency} | {tx['name']} | Ref: {tx['reference']} | {tx['time']}")
    else:
        print("⚠️ No incoming transfers today.")

    outgoing_today = await get_outgoing_transfers_csv(client, profile_id, account["id"], currency)

    if outgoing_today:
        print("📥 Outgoing transfers today:")
        for tx in outgoing_today:
            print(f"   {tx['amount']} {currency} | {tx['name']} | Ref: {tx['reference']} | {tx['time']}")
    else:
        print("⚠️ No Outgoing transfers today.")



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



async def fetch_wise_buy_ad_details(client: P2P):
    wise_buy_ad = await client.get_ad_details(itemId="1799865939992154112")
    return wise_buy_ad

async def fetch_wise_sell_ad_details(client: P2P):
    wise_sell_ad = await client.get_ad_details(itemId="1989351720308887552")
    return wise_sell_ad


# -------------------------
# AD PAYLOAD FACTORY
# -------------------------

def build_ad_payload(
    *,
    ad_id: str,
    side: int,
    price: float,
    min_amount: int,
    max_amount: int,
    remark: str,
    action_type: str,
    quantity: str = "200",
    payment_period: str = "15"
):
    """
    Creates a clean, consistent payload for update_ad().
    All the shared parameters live here to avoid duplication.
    """

    return {
        "id": ad_id,
        "priceType": 0,
        "tokenId": "USDT",
        "currencyId": "USD",
        "side": side,
        "premium": 0,
        "price": price,
        "minAmount": min_amount,
        "maxAmount": max_amount,
        "remark": remark,
        "tradingPreferenceSet": {
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
            "hasNationalLimit": 0
        },
        "paymentIds": ["21555896"],   # must be str
        "actionType": action_type,
        "quantity": quantity,
        "paymentPeriod": payment_period
    }

# TODO: Think of combining modify and activate ad

# ============================
# MODIFY BUY/SELL ADS (TEST)
# ============================

# TODO: replace with "1799865939992154112" before going live
"""Adjust: price, min/max_amount, remark"""
async def modify_wise_buy_ad(client: P2P):
    payload = build_ad_payload(
        ad_id="1977382182365315072",   # TODO replace with real ID before going live
        side=0,
        price=0.97,
        min_amount=150,
        max_amount=200,
        remark="Contact @kolya5544 on Telegram once you've paid.",
        action_type="MODIFY"
    )
    return await client.update_ad(**payload)

# TODO: replace with "1989351720308887552" before going live
"""Adjust: price, min/max_amount, remark"""
'''Optionally: Think of adjusting the price based on other seller's behavior'''
async def modify_wise_sell_ad(client: P2P):
    payload = build_ad_payload(
        ad_id="1975370069588332544",   # TODO replace with real ID
        side=1,
        price=1.05,
        min_amount=150,
        max_amount=200,
        remark="Contact @kolya5544 on Telegram once you've paid.",
        action_type="MODIFY"
    )
    return await client.update_ad(**payload)


# ============================
# ACTIVATE ADS
# ============================

# TODO: replace with "1799865939992154112" before going live
"""Adjust: price, min/max_amount, remark"""
async def activate_wise_buy_ad(client: P2P):
    payload = build_ad_payload(
        ad_id="1977382182365315072",
        side=0,
        price=0.97,
        min_amount=150,
        max_amount=200,
        remark="Contact @kol4 on Telegram once you've paid.",
        action_type="ACTIVE"
    )
    return await client.update_ad(**payload)


# TODO: replace with "1989351720308887552" before going live
"""Adjust: price, min/max_amount, remark"""
'''Optionally: Think of adjusting the price based on other seller's behavior'''
async def activate_wise_sell_ad(client: P2P):
    payload = build_ad_payload(
        ad_id="1975370069588332544",
        side=1,
        price=1.05,
        min_amount=150,
        max_amount=200,
        remark="Contact @ko44 on Telegram once you've paid.",
        action_type="ACTIVE"
    )
    return await client.update_ad(**payload)


# TODO: replace with "1799865939992154112" before going live
async def remove_wise_buy_ad(client: P2P):
    buy_ad_rem = await client.remove_ad(
        itemId="1977382182365315072"
    )
    return buy_ad_rem


# TODO: replace with "1989351720308887552" before going live
async def remove_wise_sell_ad(client: P2P):
    sell_ad_rem = await client.remove_ad(
        itemId="1975370069588332544"
    )
    return sell_ad_rem


async def fetch_pending_sell_orders(client: P2P):
    orders_raw = await client.get_pending_orders(
        side=1,
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
        side=0,
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

"""paymentType is 0 when the order is open. It's getting the correct paymentType (78) whenever its marked as paid"""
async def get_pending_sell_order_details(client: P2P):

    orders_list = await get_sell_order_id(client=client)

    if not orders_list:
        print("NO PENDING SELL ORDERS FOUND")
        return []  # no orders found

    tasks = []
    for order in orders_list:                                       #This code builds a list of coroutines but does NOT execute them yet
        tasks.append(client.get_order_details(orderId=order["orderId"]))

    details = await asyncio.gather(*tasks, return_exceptions=True)  #'.gather' takes ALL waiting tasks, launches them together, waits until ALL
                                                                    # complete and then returns results as a list in the same order as input

    result = []

    for order, detail in zip(orders_list, details):                 # zip pairs each original order dict (order) with each API result (resp)
        if isinstance(detail, Exception):                           # and combines them into the requested format
            print(f"[ERROR] Failed API call for orderId {order['orderId']}: {detail}")
            result.append({
                "orderId": order["orderId"],
                "error": str(detail)
            })
            continue

        result.append({
            "orderId": order["orderId"],
            "paymentType": detail["result"]["paymentType"]
        })

    return result

"""paymentType is 0 when the order is open. It's getting the correct paymentType (78) whenever its marked as paid"""
async def get_pending_buy_order_details(client: P2P):

    orders_list = await get_buy_order_id(client=client)

    if not orders_list:
        print("NO PENDING BUY ORDERS FOUND")
        return []  # no orders found

    tasks = []
    for order in orders_list:                                       #This code builds a list of coroutines but does NOT execute them yet
        tasks.append(client.get_order_details(orderId=order["orderId"]))

    details = await asyncio.gather(*tasks, return_exceptions=True)  #'.gather' takes ALL waiting tasks, launches them together, waits until ALL
                                                                    # complete and then returns results as a list in the same order as input

    result = []

    for order, detail in zip(orders_list, details):                 # zip pairs each original order dict (order) with each API result (resp)
        if isinstance(detail, Exception):                           # and combines them into the requested format
            print(f"[ERROR] Failed API call for orderId {order['orderId']}: {detail}")
            result.append({
                "orderId": order["orderId"],
                "error": str(detail)
            })
            continue

        result.append({
            "orderId": order["orderId"],
            "paymentType": detail["result"]["paymentType"]
        })

    return result


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

    print("Buy ad active:",
          await activate_wise_buy_ad(client=api)
          )

    print("Sell ad active:",
          await activate_wise_sell_ad(client=api)
          )

    """FOR some reason to remove/activate ad I have to shadow print("modify ads") below"""

    """REQUIRES ATTENTION!"""
    print("Modify buy ad: ",
          await modify_wise_buy_ad(client=api)
          )

    print("Modify sell ad: ",
          await modify_wise_sell_ad(client=api)
          )

    """KEEP INACTIVE SO CALLS DO NOT CONFLICT WITH EACH OTHER"""



    print("Test buy ad removed:",
          await remove_wise_buy_ad(client=api)
          )

    print("Test sell ad removed:",
          await remove_wise_sell_ad(client=api)
          )

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
            return

        profile_id = business_profile["id"]
        print(f"\n👤 Using BUSINESS Profile ID: {profile_id}")
        print("🔁 Starting continuous Wise balance & incoming transfer tracking every 30 seconds...\n")

        while True:
            await display_balance_and_transactions(client, profile_id, currency="USD")
            await asyncio.sleep(30)
        #
    # await api.close_session()



asyncio.run(main())