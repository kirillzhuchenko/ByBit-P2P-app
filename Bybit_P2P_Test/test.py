# from bybit_p2p import P2P
# import requests
#
# api = P2P(
#     testnet=True,
#     api_key="IjQCejlmaMcdhbEhy8",
#     api_secret="zpjDLwnHzGkoU7Lo0axxIXYGd5t3UPhsUbEi"
# )
#
# # 1. Get current balance
# print(api.get_current_balance(accountType="FUND", coin="USDT"))
#
# # 2. Get account information
# print(api.get_account_information())
#
# # 3. Get ads list
# print(api.get_ads_list())

test = {'ret_code': 0, 'ret_msg': 'SUCCESS', 'result': {'id': '1977382182365315072', 'accountId': '124981369', 'userId': '124981367', 'nickName': '', 'tokenId': 'USDT', 'tokenName': 'USDT', 'currencyId': 'USD', 'side': 0, 'priceType': 0, 'price': '0.970', 'premium': '0', 'lastQuantity': '2109.9942', 'quantity': '2109.9942', 'frozenQuantity': '0', 'executedQuantity': '0', 'minAmount': '100.000', 'maxAmount': '3000.000', 'remark': "1) The transaction will be handled via my sole-owned company IP ZHUCHENKO, LLC. If you disagree with this please don't open an order.\n2) Single transfer\n3) I send funds ONLY to the owner of both bybit and bank accounts.\n3) I pay within 5 minutes\n4) my Tele. @DeFi_Capital", 'status': 10, 'createDate': '1760279626000', 'payments': ['121'], 'orderNum': 18, 'finishNum': 18, 'recentOrderNum': 0, 'recentExecuteRate': 0, 'fee': '', 'isOnline': False, 'lastLogoutTime': '0', 'symbolInfo': {'id': '17', 'exchangeId': '301', 'orgId': '9001', 'tokenId': 'USDT', 'currencyId': 'USD', 'status': 1, 'lowerLimitAlarm': 80, 'upperLimitAlarm': 120, 'itemDownRange': '80', 'itemUpRange': '120', 'currencyMinQuote': '2', 'currencyMaxQuote': '50000', 'currencyLowerMaxQuote': '2', 'tokenMinQuote': '1', 'tokenMaxQuote': '50000', 'kycCurrencyLimit': '0', 'itemSideLimit': 3, 'buyFeeRate': '', 'sellFeeRate': '', 'orderAutoCancelMinute': 15, 'orderFinishMinute': 10, 'tradeSide': 9, 'currency': {'id': '17', 'exchangeId': '0', 'orgId': '9001', 'currencyId': 'USD', 'scale': 3}, 'token': {'id': '1', 'exchangeId': '0', 'orgId': '9001', 'tokenId': 'USDT', 'scale': 4, 'sequence': 1}, 'buyAd': {'paymentPeriods': [15, 30]}, 'sellAd': {'paymentPeriods': [15, 30]}}, 'tradingPreferenceSet': {'hasUnPostAd': 1, 'isKyc': 1, 'isEmail': 1, 'isMobile': 1, 'hasRegisterTime': 1, 'registerTimeThreshold': 180, 'orderFinishNumberDay30': 60, 'completeRateDay30': '95', 'nationalLimit': 'BEN', 'hasOrderFinishNumberDay30': 1, 'hasCompleteRateDay30': 1, 'hasNationalLimit': 1}, 'paymentTerms': [{'id': '21555734', 'realName': 'KIRILL ZHUCHENKO', 'paymentType': 121, 'bankName': 'BofA and Chase', 'branchName': '', 'accountNo': 'IP ZHUCHENKO LLC ', 'qrcode': '', 'visible': 0, 'payMessage': '', 'firstName': '', 'lastName': '', 'secondLastName': '', 'clabe': '', 'debitCardNumber': '', 'mobile': '818', 'businessName': '', 'concept': '', 'paymentExt1': 'ip.kz.llc@gmail.com or ip_kz_llc@yahoo.com', 'paymentExt2': '', 'paymentExt3': '', 'paymentExt4': '', 'paymentExt5': '', 'paymentExt6': '', 'paymentTemplateVersion': 5, 'paymentConfig': {'paymentType': 121, 'paymentName': 'Zelle', 'paymentDialect': 'payment_field_121', 'paymentTemplateItem': [{'labelDialect': 'input_field_bankName', 'placeholderDialect': 'input_tip_bankName', 'fieldName': 'bankName'}, {'labelDialect': 'input_field_accountNo', 'placeholderDialect': 'input_tip_accountNo', 'fieldName': 'accountNo'}, {'labelDialect': 'input_field_realName', 'placeholderDialect': 'input_tip_realName', 'fieldName': 'realName'}, {'labelDialect': 'input_field_payMessage', 'placeholderDialect': 'input_tip_paymentExt4', 'fieldName': 'mobile'}, {'labelDialect': 'input_field_paymentExt6', 'placeholderDialect': 'input_tip_email', 'fieldName': 'paymentExt1'}]}, 'realNameVerified': True}], 'version': 2, 'updateDate': '1763312439000', 'feeRate': '0', 'paymentPeriod': 30, 'itemType': 'ORIGIN', 'verificationOrderSwitch': False, 'verificationOrderLabels': [], 'verificationOrderAmount': '0', 'subsidyAd': False}, 'ext_code': '', 'ext_info': {}, 'time_now': '1763312707.861926'}
print("Ad details:", test['result'])
print("Trading preferences:", test["result"]["tradingPreferenceSet"])
print("Payment terms:", test["result"]["paymentTerms"])
print("Payment configuration:", test["result"]["paymentTerms"][0]["paymentConfig"])