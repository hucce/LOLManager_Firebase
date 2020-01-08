import json

class UserData:

    def __init__(self):
       self.rateVspoint = 0
       self.match = 0
       self.win = 0

with open('D:\JsonPyhton\lol-esports-3080c_data.json', 'r', encoding='UTF8') as file:
     json_data = json.load(file)

dic = {}
for data in json_data['Ranking']:
    userClass = UserData()
    userClass.rateVspoint = json_data['Ranking'][data]
    dic[data] = userClass

delDic = []
for data in dic:
    userdata = json_data['users'][data]
    if('matchData' in userdata):
        mathData = json_data['users'][data]["matchData"].split(',')
        userClass = dic[data]
        userClass.match = mathData[0]
        userClass.win = mathData[1]
    else:
        delDic.append(data)

for delID in delDic:
    del dic[delID]

for data in dic:
    value = dic[data]
    value = str(value.rateVspoint) + "," + str(value.match) + "," + str(value.win)
    dic[data] = value

with open('D:\JsonPyhton\exportJson.json', 'w', encoding='utf-8') as make_file:
    json.dump(dic, make_file, indent="\t")


