from shopping_agent.amazon_links import extract_asin

url = "https://www.amazon.com/dp/B085DVHQ57?lv=shuf&channelId=425&plpRedirect=mhFallback&th=1"

print(extract_asin(url))