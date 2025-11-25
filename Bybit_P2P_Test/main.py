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

async def fetch_ads_list(client: P2P): #### idk if I need this one.
    # I probably have to update the same ad continuously to meet present Wise balance.
    ads_list = await client.get_ads_list()
    wise_ad = ads_list["result"]["items"][0]
    return ads_list["result"]["items"]

async def fetch_wise_buy_ad(client: P2P): ## Not sure if I need this one
    ads_list = await fetch_ads_list(client=client)
    wise_buy_ad = ads_list[0]
    return wise_buy_ad

async def fetch_wise_sell_ad(client: P2P): ##Not sure if I need this one
    ads_list = await fetch_ads_list(client=client)
    wise_sell_ad = ads_list[1]
    return wise_sell_ad

async def fetch_wise_buy_ad_details(client: P2P):
    wise_buy_ad = await client.get_ad_details(itemId="1799865939992154112")
    return wise_buy_ad

async def fetch_wise_sell_ad_details(client: P2P):
    wise_sell_ad = await client.get_ad_details(itemId="1989351720308887552")
    return wise_sell_ad

"""DELETE TEST AD IN THE FUTURE"""
async def fetch_test_ad_details(client: P2P):
    test_ad = await client.get_ad_details(itemId="1977382182365315072")
    return test_ad

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

"""NEXT 2 func to be removed in the future, both are handled in fetch_pending_buy/sell_orders"""
async def fetch_list_of_sell_orders(client: P2P):
    list_of_orders = await client.get_orders(
        page=1,
        size=10,
        side=1
    )
    list = list_of_orders["result"]["items"]
    return list


async def fetch_bybit_counterparty_info(client: P2P):
    orders = await fetch_list_of_sell_orders(client=client)

    result = []
    for o in orders:
        entry = {
            "order_id": o["id"],
            "name": o["buyerRealName"],
            "amount": o["amount"],
        }
        result.append(entry)

    return result

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
    return msg


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
        # print("Order id: ", result)
    return result


async def get_buy_order_id(client: P2P):

    response = await fetch_pending_buy_orders(client=client)

    result = []
    for order in response:
        entry = {
            "orderId": order["order_id"],
        }

        result.append(entry)
        # print("Order id: ", result)
    return result

"""FETCHES BUY ORDERS ATM, HAVE TO CHANGE IT TO SELL ORDERS"""
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
        await fetch_balance(client=api)
          )

    print("List of ads:",
        await fetch_ads_list(client=api)
          )


    """Not sure if I need two calls from below"""
    # print("Wise buy ad is here: ",
    #       await fetch_wise_buy_ad(client=api)
    #       )
    #
    # print("Wise sell ad is here: ",
    #       await fetch_wise_sell_ad(client=api)
    #       )
    ####

    print("Wise buy ad details:",
          await fetch_wise_buy_ad_details(client=api)
          )

    print("Wise sell ad details:",
          await fetch_wise_sell_ad_details(client=api)
          )

    print("Test ad details:",
          await fetch_test_ad_details(client=api)
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

    print("Last 10 sell orders:",
          await fetch_list_of_sell_orders(client=api)
          )

    print("Counterparty info:",
          await fetch_bybit_counterparty_info(client=api)
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

    # 11. Release digital asset
    # print(await api.release_assets(
    #     orderId="1234567890123456789"
    # ))

    '''cannot use this one with USD on Wise, not sure about Revolut. Should be good with EUR'''
    # # 12. Mark order as paid
    # print(await api.mark_as_paid(
    #     orderId="1234567890123456789",
    #     paymentType="123",
    #     paymentId="5544"
    # ))

    # # 13. Get chat messages
    # print(await api.get_chat_messages(
    #     orderId="1992070819939557376",
    #     startMessageId=0,
    #     size=100
    # ))
    # print("chat messages")

    # 14. Upload chat file
    # print(await api.upload_chat_file(
    #     upload_file="D:/test.png"
    # ))

    # # 15. Send chat message
    # import uuid
    # print(await api.send_chat_message(
    #     message="Please disregard this message",
    #     contentType="str",
    #     orderId="1234567890123456789",
    #     msgUuid=uuid.uuid4().hex
    # ))

    # # 16. Post new advertisement
    # print(await api.post_new_ad(
    #     tokenId="USDT",
    #     currencyId="RUB",
    #     side="1",
    #     priceType=1,
    #     premium=90,
    #     price=78.3,
    #     minAmount=500,
    #     maxAmount=3500000,
    #     remark="Contact @kolya5544 on Telegram once you've paid.",
    #     tradingPreferenceSet={
    #             "hasUnPostAd": 0,
    #             "isKyc": 1,
    #             "isEmail": 0,
    #             "isMobile": 0,
    #             "hasRegisterTime": 0,
    #             "registerTimeThreshold": 0,
    #             "orderFinishNumberDay30": 0,
    #             "completeRateDay30": "",
    #             "nationalLimit": "",
    #             "hasOrderFinishNumberDay30": 0,
    #             "hasCompleteRateDay30": 0,
    #             "hasNationalLimit": 0
    #         },
    #     paymentIds=["6558"],
    #     quantity="25000",
    #     paymentPeriod="15",
    #     itemType="ORIGIN"
    # ))

    # # 17. Get online advertisements list
    # print(await api.get_online_ads(
    #     tokenId="USDT",
    #     currencyId="RUB",
    #     side="0",
    #     payment=["1", "377"],
    #     vaMaker=True
    # ))

    # 18. Get user payment
    print(
        await api.get_user_payment_types()
    )

    await api.close_session()





asyncio.run(main())