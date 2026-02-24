import base64
c1 = base64.b64decode(open(r"C:/url spreasheets/vs_projects/nlmapV3/_c1.b64").read().encode()).decode("utf-8")
c2 = base64.b64decode(open(r"C:/url spreasheets/vs_projects/nlmapV3/_c2.b64").read().encode()).decode("utf-8")
with open(r"C:/url spreasheets/vs_projects/nlmapV3/CAMPAIGN_BE.md", "w", encoding="utf-8") as f: f.write(c1)
with open(r"C:/url spreasheets/vs_projects/nlmapV3/FEATURES_GUIDE.md", "w", encoding="utf-8") as f: f.write(c2)
print("Both files written:", len(c1), "and", len(c2), "chars")
