import requests
from bs4 import BeautifulSoup

res = requests.get("https://suumo.jp/chintai/jnc_000100348836/?bc=100450958100")
soup = BeautifulSoup(res.text, "html.parser")
print(soup.title.text)
