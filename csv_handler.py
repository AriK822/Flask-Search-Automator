import pandas as pd
from os import mkdir, path
from db_handler import clear_cache



if not path.exists("saved_csv"):
    mkdir("saved_csv")



class CSVHandler:
    def __init__(self, data):
        self.db = pd.DataFrame(data=data, columns=["Title", "Company", "Location", "Link"])
    
    def add(self, title, company, location, link):
        self.db.loc[len(self.db)] = [title, company, location, link]

    def save(self, file_name):
        self.db.to_csv(file_name)

    def __str__(self) -> str:
        return self.db.__str__()
    


class DataFethcher:
    def __init__(self, filename):
        self.db = pd.read_csv(f"saved_csv/{filename}.csv")


    def fetch(self):
        return self.db.values



class Converter:
    def __init__(self, filename):
        self.db = pd.read_csv(f"saved_csv/{filename}.csv").drop("Unnamed: 0", axis=1)
        self.filename = filename
        clear_cache()


    def to_excel(self):
        if path.exists(f"cache/{self.filename}.xlsx"): return
        self.db.to_excel(f"cache/{self.filename}.xlsx")


    def to_html(self):
        if path.exists(f"cache/{self.filename}.hmtl"): return
        self.db.to_html(f"cache/{self.filename}.html")


    def to_json(self):
        if path.exists(f"cache/{self.filename}.json"): return
        self.db.to_json(f"cache/{self.filename}.json")




if __name__ == "__main__":
    # handler = CSVHandler([
    # ("qw", 23, 34, 56),
    # ("qw", 23, 3344, 56),
    # ("dvber", 23, "34", 56),
    # ])
    # handler.add("fgdb", 23, 8564, 56)

    # print(handler)
    # handler.save("ttt")

    # handler = DataFethcher("1234 1")
    # handler.fetch()

    Converter("1234 1").to_excel()


