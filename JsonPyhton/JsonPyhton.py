import json

class UserData:

    def __init__(self):
       self.rateVspoint = 0
       self.match = 0
       self.win = 0

def AllSeasonfile():
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

def RankerDataFile():
        with open('D:\JsonPyhton\lol-esports-3080c_data.json', 'r', encoding='UTF8') as file:
            json_data = json.load(file)

        with open('D:\JsonPyhton\sesonRanker.json', 'r',) as file:
            json_ranking = json.load(file)

        rankdata = json_data['Ranking']
        userdata = json_data['users']
        namedata = json_data['TeamName']

        for data in json_ranking:
            dic = {}
            dic['teamName'] = namedata[data]
            dic['reteVsPoint'] = rankdata[data]
            mathData = userdata[data]["matchData"].split(',')
            dic['match'] = mathData[0]
            dic['win'] = mathData[1]
            dic['topPlayerIDTrait'] = userdata[data]['topPlayerIDTrait']
            dic['junglePlayerIDTrait'] = userdata[data]['junglePlayerIDTrait']
            dic['midPlayerIDTrait'] = userdata[data]['midPlayerIDTrait']
            dic['adPlayerIDTrait'] = userdata[data]['adPlayerIDTrait']
            dic['supPlayerIDTrait'] = userdata[data]['supPlayerIDTrait']
            dic['managerSet'] = userdata[data]['managerSet']
            json_ranking[data] = dic

        with open('D:\JsonPyhton\exportRakers.json', 'w', encoding='UTF8') as make_file:
            json.dump(json_ranking, make_file, indent="\t", ensure_ascii = False)

def BenList():
        with open('D:\JsonPyhton\First_data.json', 'r', encoding='UTF8') as file:
            json_data = json.load(file)

        bendata = json_data['data']['BenList']

        with open('D:\JsonPyhton\exportBenList.json', 'w', encoding='UTF8') as make_file:
            json.dump(bendata, make_file, indent="\t", ensure_ascii = False)

def RankerDataSeasonFile():
        with open('D:\JsonPyhton\lol-esports-3080c_data.json', 'r', encoding='UTF8') as file:
            json_data = json.load(file)
        
        with open('D:\JsonPyhton\sesonRanker.json', 'r', encoding='UTF8') as file:
            json_ranker = json.load(file)

        rankdata = json_data['Ranking']
        userdata = json_data['users']

        rank = 1
        for ranker in json_ranker:
            row = userdata[ranker]['matchData'].split(',')
            json_ranker[ranker] = str(rankdata[ranker]) + ',' + row[0] + ',' + row[1] + ',' + str(rank)
            rank +=1

        with open('D:\JsonPyhton\exportRaker.json', 'w', encoding='UTF8') as make_file:
            json.dump(json_ranker, make_file, indent="\t", ensure_ascii = False)

def AllRankZero():
        with open('D:\JsonPyhton\RecentRanking.json', 'r', encoding='UTF8') as file:
            json_data = json.load(file)

        with open('D:\JsonPyhton\exportBenList.json', 'r', encoding='UTF8') as file:
            json_Bendata = json.load(file)
        
        for data in json_data:
            json_data[data] = 0

        for data in json_Bendata:
            if data in json_data:
                del json_data[data]

        with open('D:\JsonPyhton\exprotRankZero.json', 'w', encoding='UTF8') as make_file:
            json.dump(json_data, make_file, indent="\t", ensure_ascii = False)

def DataFile():
        with open('D:\JsonPyhton\First_data.json', 'r', encoding='UTF8') as file:
            json_data = json.load(file)

        dataData = json_data['data']

        with open('D:\JsonPyhton\TestData.json', 'w', encoding='UTF8') as make_file:
            json.dump(dataData, make_file, indent="\t", ensure_ascii = False)

DataFile()