import json
import time

import requests
import schedule

from operator import itemgetter
import os

# Twitter api is initialized in config.py with tweepy lib. 
# Importing it as twitter to send tweets.
from files.config import api as twitter

# https://defillama.com/docs/api

# https://api.llama.fi/charts
# https://api.llama.fi/charts/avalanche
# https://api.llama.fi/charts/ethereum
# https://api.llama.fi/chains


def get_asset_price(cgecko_id: str):
    """function to get price of an asset using CoinGeckoID"""
    
    request = requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={cgecko_id}&vs_currencies=usd").json()
    return f"{cgecko_id.upper()} / USD {request[cgecko_id]['usd']} $"

def telegram_message(msg: str, channel="TELEGRAM_CHANNEL"):
    """Function to send a message on telegram."""
    requests.get(f"https://api.telegram.org/BOT_TOKEN/sendMessage?chat_id={channel}&text={msg}")

#############################################################################################################################

def save_existing_protocols():
    """function to save existing DefiLlama protocols 
    and their Data onto a protocols.json file in order to use it later"""
    
    data = dict()
    # Getting list of protocols with DefiLlama API
    all_protocols = requests.get('https://api.llama.fi/protocols').json()
    
    # Getting id, name, and chains of protocols currently listed and writing it to a file
    for protocol in all_protocols:
            id = protocol["id"]
            name = protocol["name"]
            chains = protocol["chains"]
            data[id] = {"name": name,
                        "chains": chains}
    
    with open("files/protocols.json", "w", encoding="utf8") as file:
        json.dump(data, file, indent=4)
        print("Data file created / updated.")


#############################################################################################################################


def check_protocol_chains(new_data: dict):
    """function to check if a protocol is available
    on new chains, and sending a tweet
    
    new_data = updated list of protocols returned by the API"""
    
    # Opening protocols.json to get old data about protocols
    with open("files/protocols.json", "r", encoding="utf8") as file:
        old_data = json.load(file)
    changes = 0

    # Comparing new data with old data
    for protocol in new_data:
        id = protocol["id"]
        chains = protocol["chains"]
        
        # Updating protocols.json if protocol not already saved then continue the loop
        if id not in old_data:
            with open("files/protocols.json", "r+", encoding="utf8") as file:
                protocol[id] = {"name": protocol["name"],
                            "chains": protocol["chains"]}
                file.seek(0)
                json.dump(old_data, file, indent=4)
                file.truncate()
            print(protocol["name"], "added to protocols.json")
            continue
        
        # Compare
        new_chains = list()
        for chain in chains:
            if chain not in old_data[id]["chains"]:
                new_chains.append(chain)
        
        # Checking if there is a new chain added
        if new_chains:
            # Retrieving protocol URL on DefiLlama with its slug
            url = 'https://defillama.com/protocol/' + protocol['slug']
            
            # Using protocol Twitter name if available
            name = f"@{protocol['twitter']}" if protocol["twitter"] else protocol["name"]
            
            # Getting asset price if gecko_id is available
            price = get_asset_price(protocol["gecko_id"]) if protocol["gecko_id"] else ""
            
            # Sending tweet about the new chain
            twitter.update_status(f"🛠 {name} is now available on #{' / #'.join(new_chains)} 🔥\n\n"
                                f"{price}\n\n{url}")

            # Updating chains list of this protocol in protocols.json
            old_data[id]["chains"] = protocol["chains"]
        
            print(f"{', '.join(new_chains)} added to {name}")
            changes += 1
        
    # If some changes were applied, updating protocols.json
    if changes:
        with open("files/protocols.json", "r+", encoding="utf8") as file:
            file.seek(0) 
            json.dump(old_data, file, indent=4)
            file.truncate()
    elif not changes:
        print("No new chains.")
        

def check_new_protocols(new_data: dict):
    """Function to check if a new protocol has been added
    on DefiLlama API
    
    new_data = updated list of protocols returned by the API"""
    
    # Opening protocols.json to get old data about protocols
    with open("files/protocols.json", "r", encoding="utf8") as file:
        old_data = json.load(file)
    
    # Looping through updated list of protocols and compare it with currently saved protocols
    for protocol in new_data:
        id = protocol["id"]
        
        if id not in old_data:
            name =  f"@{protocol['twitter']}" if protocol["twitter"] else protocol["name"]
            description = f"{protocol['description'][:100]} [...]"
            chains = ", ".join(protocol["chains"])
            url = protocol["url"]
            audits = "\n".join(protocol["audit_links"]) if int(protocol['audits']) else "No audits."
            chains_tvl = "\n".join([f"{chain}: {round(int(tvl), 0):,d} $" for chain, tvl in protocol["chainTvls"].items() if tvl > 0])
            
            price = get_asset_price(protocol["gecko_id"]) if protocol["gecko_id"] else ""
            
            # Sending tweet
            try:
                tweet = twitter.update_status(f"🎯 Now tracking {name} on DefiLlama 🦙\n\n"
                                          f"{description}\n\n"
                                          f"🌐 Network(s): {chains}\n\n{price}\n{url}")

                tweet2 = (f"⚙ Audits {audits}\n\n"
                          f"TVL ⤵️️\n{chains_tvl}")

                time.sleep(3)
                twitter.update_status(status=tweet2, in_reply_to_status_id=tweet.id, auto_populate_reply_metadata=True)
                
                # Adding the new protocol to protocols.json
                old_data[id] = {"name": protocol["name"],
                                "chains": protocol["chains"]}
                with open("files/protocols.json", "w", encoding="utf8") as file:
                    json.dump(old_data, file, indent=4)
                    print("protocols.json updated.")
                
            except Exception as err:
                telegram_message(f"⚠️ Could not send Tweet about {name}\n\n{err}")


#############################################################################################################################


def tvl_change(new_data: dict, side: str, duration: str):
    """function to get name, chains and % change of TVL Winner or Loser
    of the day / week.
    
    new_data = API response with fresh protocols data
    side = winner or loser
    duration = daily or weekly"""
    
    # Converting duration to fit API
    api_duration = "change_1d" if duration == "daily" else "change_7d" if duration == "weekly" else ""
    
    # Applying max() function on TVL % change of all protocols
    if side == "winner":
        # res contains the slug and % change of the winner
        res = max([(entry["slug"], entry[api_duration]) for entry in new_data if entry[api_duration]], key=itemgetter(1))
        evolution = "increase !  🚀"
    
    elif side == "loser":
        # res contains the slug and % change of the loser
        res = min([(entry["slug"], entry[api_duration]) for entry in new_data if entry[api_duration] and entry["tvl"]], key=itemgetter(1))
        evolution = "decrease ... 📉"
    
    else:
        return "Wrong side."
        
    slug = res[0]
    percent_change = res[1]
    
    # Getting informations about the protocol with it's slug
    protocol = requests.get(f"https://api.llama.fi/protocol/{slug}").json()
    
    name = f"@{protocol['twitter']}" if protocol["twitter"] else protocol["name"].capitalize()
    chains = '# '.join(protocol["chains"])
    token_price = get_asset_price(protocol["gecko_id"]) if protocol["gecko_id"] else ""
    tvl = requests.get(f"https://api.llama.fi/tvl/{slug}").json()
    
    # Sending tweet
    twitter.update_status(f"🦙 {duration.capitalize()} #TVL {side} is {name} with a {round(int(percent_change), 0)} % {evolution}\n\n"
                            f"🔐 Its TVL is now {round(int(float(tvl)), 2): ,d} $ 💵 across #{chains}.\n\n{token_price}\n\n"
                            f"https://defillama.com/protocol/{slug}")
    
    print(f"{duration} {side} tweet sent.")


def no_tvl(new_data: dict):
    """Function to send a notification on telegram when a protocol
    on DefiLlama has a TVL of 0$"""
    
    # Opening file with all 0 TVL protocols saved, creating it if it doesn't exist
    if not path.exists("files/no_tvl.json"):
        with open("files/no_tvl.json", "w", encoding="utf8") as file:
            json.dump({"ids": []}, file)

    with open("files/no_tvl.json", "r+", encoding="utf8") as file:
        no_tvl = json.load(file)

        count = 0
        # Looping through all protocols to check if their TVL is equal to 0
        for protocol in new_data:
            if protocol['tvl'] == 0 and protocol['id'] not in no_tvl:
                url = 'https://defillama.com/protocol/' + protocol['slug']
                
                # Sending notification on telegram
                telegram_message(f"{protocol['name']} has a TVL of {protocol['tvl']} $ \n\n"
                                 f"{url}\n\n{protocol['url']}")
                
                no_tvl["ids"].append(protocol["id"])
                count += 1
                
        file.seek(0)
        json.dump(no_tvl, file)
        file.truncate()
        print(count, "protocols with 0 TVL.")


#############################################################################################################################

    
def protocols_checks(): 
    updated_data = requests.get('https://api.llama.fi/protocols').json()
    check_new_protocols(updated_data)

def tvl_checks():
    updated_data = requests.get('https://api.llama.fi/protocols').json()
    checks = [("winner", "daily"), ("loser", "daily"), ("winner", "weekly"), ("loser", "weekly")]
    for side, duration in checks:
        tvl_change(updated_data, side, duration)
        time.sleep(1)
        # time.sleep(35)



# Creating necessary folders and files
if not os.path.isdir("files"):
        os.mkdir("files")

if not os.path.exists("files/protocols.json"):
    save_existing_protocols()


# schedule.every(2).days.do(check_tvl)

# while True:
#     schedule.run_pending()
#     time.sleep(1)

