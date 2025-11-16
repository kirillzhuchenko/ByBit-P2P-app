from async_bybit_p2p import P2P
import asyncio
import os


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




    # 7. Get Orders
    print(await api.get_orders(
        page=1,
        size=10
    ))
    print("Orders above")

    # 8. Get Pending Orders
    print(await api.get_pending_orders(
        page=1,
        size=10
    ))

    # 9. Get counterparty info
    print(await api.get_counterparty_info(
        originalUid="118027304",
        orderId="1957477110433914880"
    ))

    # 10. Get order details
    print(await api.get_order_details(
        orderId="1983711568542887936"
    ))
    print("order details last one")

    # 11. Release digital asset
    print(await api.release_assets(
        orderId="1234567890123456789"
    ))

    # 12. Mark order as paid
    print(await api.mark_as_paid(
        orderId="1234567890123456789",
        paymentType="123",
        paymentId="5544"
    ))

    # 13. Get chat messages
    print(await api.get_chat_messages(
        orderId="1957477110433914880",
        startMessageId=0,
        size=100
    ))
    print("chat messages")

    # 14. Upload chat file
    print(await api.upload_chat_file(
        upload_file="D:/test.png"
    ))

    # 15. Send chat message
    import uuid
    print(await api.send_chat_message(
        message="Hello, please send funds to the bank account specified",
        contentType="str",
        orderId="1234567890123456789",
        msgUuid=uuid.uuid4().hex
    ))

    # 16. Post new advertisement
    print(await api.post_new_ad(
        tokenId="USDT",
        currencyId="RUB",
        side="1",
        priceType=1,
        premium=90,
        price=78.3,
        minAmount=500,
        maxAmount=3500000,
        remark="Contact @kolya5544 on Telegram once you've paid.",
        tradingPreferenceSet={
                "hasUnPostAd": 0,
                "isKyc": 1,
                "isEmail": 0,
                "isMobile": 0,
                "hasRegisterTime": 0,
                "registerTimeThreshold": 0,
                "orderFinishNumberDay30": 0,
                "completeRateDay30": "",
                "nationalLimit": "",
                "hasOrderFinishNumberDay30": 0,
                "hasCompleteRateDay30": 0,
                "hasNationalLimit": 0
            },
        paymentIds=["6558"],
        quantity="25000",
        paymentPeriod="15",
        itemType="ORIGIN"
    ))

    # 17. Get online advertisements list
    print(await api.get_online_ads(
        tokenId="USDT",
        currencyId="RUB",
        side="0",
        payment=["1", "377"],
        vaMaker=True
    ))

    # 18. Get user payment
    print(
        await api.get_user_payment_types()
    )

    await api.close_session()





asyncio.run(main())