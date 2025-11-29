'''cannot use mark_as_paid() with USD on Wise, not sure about Revolut. Should be good with EUR'''

"""Removed func():
fetch_test_ad_details(), fetch_ads_list(), fetch_wise_buy_ad(), fetch_wise_sell_ad(), fetch_list_of_sell_orders(),
fetch_bybit_counterparty_info()"""


from async_bybit_p2p import P2P
import asyncio
import os
import uuid


async def fetch_balance(client: P2P):
    current_balance = await client.get_current_balance(
        accountType="FUND",
        currency="USDT"
    )
    present_balance = current_balance["result"]["balance"][2]["transferBalance"]
    return present_balance


async def fetch_wise_buy_ad_details(client: P2P):
    wise_buy_ad = await client.get_ad_details(itemId="1799865939992154112")
    return wise_buy_ad

async def fetch_wise_sell_ad_details(client: P2P):
    wise_sell_ad = await client.get_ad_details(itemId="1989351720308887552")
    return wise_sell_ad



"""USES TEST AD AT THIS MOMENT, HAVE TO CHANGE TO REAL ONE BEFORE GO LIVE"""
async def modify_wise_buy_ad(client: P2P):  #Uses test ad at this stage
    buy_ad_mod = await client.update_ad(
        id="1977382182365315072",   # Replace with Wise buy ad in the future
        priceType=0,
        tokenId="USDT",
        currencyId="USD",
        side=0,
        premium=0,  # these values can all be either int or str, library handles it automatically
        price=0.97, # Adjust price before going live
        minAmount=150,
        maxAmount=200,
        remark="Contact @kolya5544 on Telegram once you've paid.",  # Remark shall be changed in the future
        tradingPreferenceSet={
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
        paymentIds=["21555896"],  # has to be str
        actionType="MODIFY",  # use ACTIVE to just reactivate the ad
        quantity="200",
        paymentPeriod="15"
    )
    return buy_ad_mod

"""USES TEST AD AT THIS MOMENT, HAVE TO CHANGE TO REAL ONE BEFORE GO LIVE"""
async def modify_wise_sell_ad(client: P2P):
    sell_ad_mod = await client.update_ad(
        id="1975370069588332544",  # Repalce with Wise sell ad in the future
        priceType=0,
        tokenId="USDT",
        currencyId="USD",
        side=1,
        premium=0,  # these values can all be either int or str, library handles it automatically
        price=1.05, # Adjust price before going live
        minAmount=150,
        maxAmount=200,
        remark="Contact @kolya5544 on Telegram once you've paid.",  # Remark shall be changed in the future
        tradingPreferenceSet={
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
        paymentIds=["21555896"],  # has to be str
        actionType="MODIFY",  # use ACTIVE to just reactivate the ad
        quantity="200",
        paymentPeriod="15"
    )
    return sell_ad_mod

"""USES TEST AD AT THIS MOMENT, HAVE TO CHANGE TO REAL ONE BEFORE GO LIVE"""
async def activate_wise_buy_ad(client: P2P):
    buy_ad_act = await client.update_ad(
        id="1977382182365315072",  # Replace with Wise buy ad in the future
        priceType=0,
        tokenId="USDT",
        currencyId="USD",
        side=0,
        premium=0,  # these values can all be either int or str, library handles it automatically
        price=0.97,  # Adjust price before going live
        minAmount=150,
        maxAmount=200,
        remark="Contact @kol4 on Telegram once you've paid.",  # Remark shall be changed in the future
        tradingPreferenceSet={
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
        paymentIds=["21555896"],  # has to be str
        actionType="ACTIVE",  # use ACTIVE to just reactivate the ad
        quantity="200",
        paymentPeriod="15"
    )
    return buy_ad_act

"""USES TEST AD AT THIS MOMENT, HAVE TO CHANGE TO REAL ONE BEFORE GO LIVE"""
async def activate_wise_sell_ad(client: P2P):
    sell_ad_act = await client.update_ad(
        id="1975370069588332544",  # Repalce with Wise sell ad in the future
        priceType=0,
        tokenId="USDT",
        currencyId="USD",
        side=1,
        premium=0,  # these values can all be either int or str, library handles it automatically
        price=1.05, # Adjust price before going live
        minAmount=150,
        maxAmount=200,
        remark="Contact @ko44 on Telegram once you've paid.",  # Remark shall be changed in the future
        tradingPreferenceSet={
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
        paymentIds=["21555896"],  # has to be str
        actionType="ACTIVE",  # use ACTIVE to just reactivate the ad
        quantity="200",
        paymentPeriod="15"
    )
    return sell_ad_act

"""USES TEST AD, REPLACE WITH WISE BUY AD BEFORE GOING LIVE"""
async def remove_wise_buy_ad(client: P2P):
    buy_ad_rem = await client.remove_ad(
        itemId="1977382182365315072"
    )
    return buy_ad_rem

"""USES TEST AD, REPLACE WITH WISE SELL AD BEFORE GOING LIVE"""
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
        """HAVE TO ADD {wisetag} AND {payment_link} AFTER ADDING THEM MAIN.PY"""
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
                        f"📩If you have any questions, feel free to contact me on Telegram: @@DeFi_Capital📩"),
                contentType="str",
                orderId=order_id,
                msgUuid=uuid.uuid4().hex,
            )
            print("Response:", response)
        except Exception as e:
            print(f"Failed to send message to order {order_id} -> {e}")

    print("All messages sent")

"""FETCHES BUY ORDERS, REMEMBER TO CHANGE IT TO FETCH SELL ORDERS"""
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
    # wise_api = P2P(
    #     api_token=os.getenv("API_TOKEN"),
    #     base_url=os.getenv("BASE_URL"),
    # )

    print("Current balance in USDT:",
        await fetch_balance(client=api)
          )


    print("Wise buy ad details:",
          await fetch_wise_buy_ad_details(client=api)
          )

    print("Wise sell ad details:",
          await fetch_wise_sell_ad_details(client=api)
          )


    """FOR some reason to remove/activate ad I have to shadow print("mod ads") below"""

    """REQUIRES ATTENTION!"""
    # print("Modify buy ad: ",
    #       await modify_wise_buy_ad(client=api)
    #       )
    #
    # print("Modify sell ad: ",
    #       await modify_wise_sell_ad(client=api)
    #       )

    """KEEP INACTIVE SO CALLS DO NOT CONFLICT WITH EACH OTHER"""

    print("Buy ad active:",
          await activate_wise_buy_ad(client=api)
          )

    print("Sell ad active:",
          await activate_wise_sell_ad(client=api)
          )

    print("Test buy ad removed:",
          await remove_wise_buy_ad(client=api)
          )

    print("Test sell ad removed:",
          await remove_wise_sell_ad(client=api)
          )



    print("Fetch last 20 Pending sell orders:",
          await fetch_pending_sell_orders(client=api)
          )

    print("Fetch last 20 Pending buy orders:",
          await fetch_pending_buy_orders(client=api)
          )

    print("Chat message:",
          await get_chat_message(client=api)
          )

    print("Message sent:",
          await send_chat_message(client=api)
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
        orderId="1993151227714883584"
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


    await api.close_session()





asyncio.run(main())