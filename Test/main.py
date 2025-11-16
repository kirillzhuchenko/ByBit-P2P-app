from bybit_p2p import P2P
import requests

api = P2P(
    testnet=True,
    api_key="IjQCecdhbEhy8",
    api_secret="zEi"
)

# 1. Get current balance
print(api.get_current_balance(accountType="FUND", coin="USDT"))

# 2. Get account information
print(api.get_account_information())

# 3. Get ads list
print(api.get_ads_list())
