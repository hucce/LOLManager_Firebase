import json

with open('D:\JsonPyhton\lol-esports-3080c-Ranking-export.json', 'r') as file:
     json_data = json.load(file)

for data in json_data:
    json_data[data] = 0;

with open('D:\JsonPyhton\export.json', 'w', encoding='utf-8') as make_file:
    json.dump(json_data, make_file, indent="\t")
