import json
from pickle import FALSE
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
from firebase_admin import auth
import pandas as pd
from datetime import datetime
from tqdm import tqdm

def FirebaseSeason(currentSeason):
    cred = credentials.Certificate("lol-esports-3080c-firebase-adminsdk-80b6e-851af7998b.json")
    firebase_admin.initialize_app(cred,{
        'databaseURL' : "https://lol-esports-3080c.firebaseio.com/"
    })
    dir = db.reference()

    json_data = dir.get()
    rankdata = json_data['Ranking']
    userdata = json_data['users']
    seasondata = json_data['SeasonDatas']
    teamName = json_data['TeamName']

    # 정렬
    res = sorted(rankdata.items(), reverse=True, key=lambda item: int(item[1]))
    json_ranker = dict(res)
    
    # 정렬한 것을 토대로 값을 변경한다
    rank = 1
    # 시즌데이터
    for ranker in json_ranker:
        if 'matchData' in userdata[ranker]:
            if 'Season' in userdata[ranker]:
                row = userdata[ranker]['matchData'].split(',')
                writeDic = seasondata[ranker]
                writeDic[currentSeason] = str(json_ranker[ranker]) + ',' + row[0] + ',' + row[1] + ',' + str(rank)
                seasondata[ranker] = writeDic
                rank +=1

    # 매치데이터
    matchDic = {}
    for ranker in json_ranker:
        matchDic[ranker] = "0,0,0,0"

    # 랭크
    rankDic = {}
    for ranker in json_ranker:
        rankDic[ranker] = 0

    WriteTop10MatchTeams(json_ranker, userdata, teamName)

    # 업데이트
    dir.child('MatchDatas').update(matchDic)
    dir.child('Ranking').update(rankDic)
    dir.child('SeasonDatas').update(seasondata)

def Export(currentSeason, serverUP):
    with open('./lol-esports-3080c_data.json', 'r', encoding='UTF8') as file:
        json_data = json.load(file)
    
    rankdata = json_data['Ranking']
    matchdata = json_data['MatchDatas']
    userdata = json_data['users']
    seasondata = json_data['SeasonDatas']
    teamName = json_data['TeamName']

    # 정렬
    res = sorted(rankdata.items(), reverse=True, key=lambda item: int(item[1]))
    json_ranker = dict(res)
    
    # 정렬한 것을 토대로 값을 변경한다
    rank = 1
    # 시즌데이터
    for ranker in json_ranker:
        # 매치 데이터가 있는 지 확인한다.
        if ranker in matchdata:
            row = matchdata[ranker].split(',')
            # 10전 이상
            if int(row[0]) > 9:
                # 기존 시즌데이터가 있는지 확인한다.
                writeDic = {}
                if ranker in seasondata:
                    writeDic = seasondata[ranker]

                # LP, 매치, 승리, 랭킹
                writeDic[currentSeason] = str(json_ranker[ranker]) + ',' + row[0] + ',' + row[1] + ',' + str(rank)
                seasondata[ranker] = writeDic
                rank +=1

    # 매치데이터
    matchDic = {}
    for ranker in json_ranker:
        matchDic[ranker] = "0,0,0,0"

    # 랭크
    rankDic = {}
    for ranker in json_ranker:
        rankDic[ranker] = 0

    with open('./Backup/exportMatch.json', 'w', encoding='utf-8') as make_file:
        json.dump(matchDic, make_file, indent="\t")
    with open('./Backup/exportSeason.json', 'w', encoding='utf-8') as make_file:
        json.dump(seasondata, make_file, indent="\t")
    with open('./Backup/exportRank.json', 'w', encoding='utf-8') as make_file:
        json.dump(rankDic, make_file, indent="\t")

    WriteTop10MatchTeams(json_ranker, userdata, teamName, matchdata)

    print('서버전 백업 완료')

    if serverUP == True:
        # 서버에 업데이트
        cred = credentials.Certificate("lol-esports-3080c-firebase-adminsdk-80b6e-851af7998b.json")
        firebase_admin.initialize_app(cred,{
            'databaseURL' : "https://lol-esports-3080c.firebaseio.com/"
        })
        dir = db.reference()
        # 업데이트
        dir.child('MatchDatas').update(matchDic)
        print('매치데이터 서버 업로드')
        dir.child('SeasonDatas').update(seasondata)
        print('시즌 서버 완료')
        dir.child('Ranking').update(rankDic)
        print('랭킹 서버 완료')

def WriteTop10MatchTeams(json_ranker, userdata, teamName, matchdata):
    #Top 10 한다.
    matchTeams = pd.read_csv('./MatchTeams.csv', encoding = 'utf-8-sig')
    ranking = 0
    for ranker in json_ranker:
        if ranking < 10:
            user = userdata[ranker]
            
            newData = {}
            newData['teamID'] = ""
            newData['teamMultiID'] = ranker
            newData['teamName'] = teamName[ranker]
            newData['category'] = ""
            newData['topPlayerIDTrait'] = user['topPlayerIDTrait']
            newData['junglePlayerIDTrait'] = user['junglePlayerIDTrait']
            newData['midPlayerIDTrait'] = user['midPlayerIDTrait']
            newData['adPlayerIDTrait'] = user['adPlayerIDTrait']
            newData['supPlayerIDTrait'] = user['supPlayerIDTrait']
            newData['managerSet'] = user['managerSet']
            # 코치
            if 'CoachList' in user:
                for c in range(3):
                   newData['coach' + str(c)] = user['CoachList'][str(c)]

            # 매치데이터
            row = matchdata[ranker].split(',')
            newData['match'] = row[0]
            newData['win'] = row[1]

            newData['rateVsPoint'] = json_ranker[ranker]
            newData = pd.DataFrame.from_dict([newData])
            matchTeams = pd.concat([matchTeams, newData])
            ranking +=1
        else:
            break
           
    matchTeams.to_csv('./MatchTeamsCopy.csv', mode='w', index=False, encoding='utf-8-sig')

def BalanceCheck():
    with open('./lol-esports-3080c_data.json', 'r', encoding='UTF8') as file:
        json_data = json.load(file)
    rankdata = json_data['Ranking']
    res = sorted(rankdata.items(), reverse=True, key=lambda item: int(item[1]))
    json_ranker = dict(res)
    users = json_data['users']
    avgDF = pd.DataFrame(data=[],columns = ['UID', 'Top', 'Jun', 'mid', 'ad', 'sup', 'total'])
    # 정렬후 확인 탑 100까지만
    rank = 1
    for ranker in json_ranker:
        # 분류 방법
        statList = []
        try:
            statList.append(CheckTrait(json_data['users'][ranker]['topPlayerIDTrait']))
            statList.append(CheckTrait(json_data['users'][ranker]['junglePlayerIDTrait']))
            statList.append(CheckTrait(json_data['users'][ranker]['midPlayerIDTrait']))
            statList.append(CheckTrait(json_data['users'][ranker]['adPlayerIDTrait']))
            statList.append(CheckTrait(json_data['users'][ranker]['supPlayerIDTrait']))
            # 각각의 라인을 분류한거를 합친다.
            plus = [0,0,0,0,0]
            for j in range(0, len(statList)):
                plus[statList[j] -1] += 1

            total = plus.index(max(plus))
        
            appendAvgDF = pd.DataFrame(data=[(str(ranker), statList[0], statList[1], statList[2], statList[3], statList[4], total)],columns = ['UID', 'Top', 'Jun', 'mid', 'ad', 'sup', 'total'])
            avgDF = pd.concat([avgDF, appendAvgDF])
            print("문제 없음: " + str(ranker))
        except:
            print("문제가 있음: " + str(ranker))
        rank += 1
        if rank > 100:
            break

    avgDF.to_csv('./balance.csv', mode='w', index=False, encoding='utf-8-sig')
    
def BalanceCheck2():
    with open('./lol-esports-3080c_data.json', 'r', encoding='UTF8') as file:
        json_data = json.load(file)
    rankdata = json_data['Ranking']
    res = sorted(rankdata.items(), reverse=True, key=lambda item: int(item[1]))
    json_ranker = dict(res)
    users = json_data['users']
    avgDF = pd.DataFrame(data=[],columns = ['UID', 'Top_Lane', 'Top_Team', 'Top_Oper', 'Jun_Lane', 'Jun_Team', 'Jun_Oper','Mid_Lane','Mid_Team','Mid_Oper','AD_Lane','AD_Team','AD_Oper','Sup_Lane','Sup_Team', 'Sup_Oper'])
    # 정렬후 확인 탑 100까지만
    rank = 1
    for ranker in json_ranker:
        # 분류 방법
        statList = []
        try:
            statList.append(CheckTrait2(json_data['users'][ranker]['topPlayerIDTrait']))
            statList.append(CheckTrait2(json_data['users'][ranker]['junglePlayerIDTrait']))
            statList.append(CheckTrait2(json_data['users'][ranker]['midPlayerIDTrait']))
            statList.append(CheckTrait2(json_data['users'][ranker]['adPlayerIDTrait']))
            statList.append(CheckTrait2(json_data['users'][ranker]['supPlayerIDTrait']))

            appendAvgDF = pd.DataFrame(data=[(str(ranker), statList[0][0], statList[0][1], statList[0][2], statList[1][0], statList[1][1], statList[1][2], statList[2][0], statList[2][1], statList[2][2], statList[3][0], statList[3][1], statList[3][2], statList[4][0], statList[4][1], statList[4][2])],columns =['UID', 'Top_Lane', 'Top_Team', 'Top_Oper', 'Jun_Lane', 'Jun_Team', 'Jun_Oper','Mid_Lane','Mid_Team','Mid_Oper','AD_Lane','AD_Team','AD_Oper','Sup_Lane','Sup_Team', 'Sup_Oper'])
            avgDF = pd.concat([avgDF, appendAvgDF])
            print("문제 없음: " + str(ranker))
        except:
            print("문제가 있음: " + str(ranker))
        rank += 1
        if rank > 101:
            break

    avgDF.to_csv('./balance2.csv', mode='w', index=False, encoding='utf-8-sig')

def CheckTrait(_trait):
    # 1,2,3
    lane = int(_trait[5:7])
    teamfight = int(_trait[7:9])
    operation = int(_trait[9:11])
    # 분류한다. 12345
    laneOper = lane + operation
    teamOper = teamfight + operation
    com = laneOper - teamOper
    cal = 3
    # 라인운영이 더 높음
    if com >= 10:
        cal = 0
    elif com >= 5:
        cal = 1
    elif com >= 2:
        cal = 2
    elif com <= -10:
        cal = 6
    elif com <= -5:
        cal = 5
    elif com <= -2:
        cal = 4

    return cal

def CheckTrait2(_trait):
    # 1,2,3
    lane = int(_trait[5:7])
    teamfight = int(_trait[7:9])
    operation = int(_trait[9:11])

    cal = []
    cal.append(lane)
    cal.append(teamfight)
    cal.append(operation)

    return cal

class UserData:

    def __init__(self):
       self.rateVspoint = 0
       self.match = 0
       self.win = 0

def AllSeasonfile():
    with open('./content/lol-esports-3080c_data.json', 'r', encoding='UTF8') as file:
         json_data = json.load(file)

    dic = {}
    # 랭킹데이터를 클래스에 넣는다.
    for data in json_data['Ranking']:
        userClass = UserData()
        userClass.rateVspoint = json_data['Ranking'][data]
        dic[data] = userClass

    # 유저데이터의 메치데이터를 클래스에 넣는다.
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

    # 매치데이터가 없는 사람은 삭제
    for delID in delDic:
        del dic[delID]

    for data in dic:
        value = dic[data]
        value = str(value.rateVspoint) + "," + str(value.match) + "," + str(value.win)
        dic[data] = value

    with open('./content/exportJson.json', 'w', encoding='utf-8') as make_file:
        json.dump(dic, make_file, indent="\t")

def Season2020file(_season):
    with open('./content/lol-esports-3080c_data.json', 'r', encoding='UTF8') as file:
         json_data = json.load(file)

    dic = {}
    # 랭킹데이터를 클래스에 넣는다.
    for data in json_data['Ranking']:
        userClass = UserData()
        userClass.rateVspoint = json_data['Ranking'][data]
        dic[data] = userClass

    # 유저데이터의 메치데이터를 클래스에 넣는다.
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

    # 매치데이터가 없는 사람은 삭제
    for delID in delDic:
        del dic[delID]

    # 유저시즌 데이터
    seasonDatas = json_data['SeasonDatas']

    for data in dic:
        value = dic[data]
        value = str(value.rateVspoint) + "," + str(value.match) + "," + str(value.win)
        dic[data] = value
        # 기존 시즌데이터에 있는지 확인한다.
        if data in seasonDatas:
            # 있으면 기존꺼에 추가한다.
            befoData = seasonDatas[data]
            befoData[_season] = value
            seasonDatas[data] = befoData
        else:
            # 없으면 새로만든다.
            newDic = {}
            newDic[_season] = value
            seasonDatas[data] = newDic

    with open('./content/exportJson.json', 'w', encoding='utf-8') as make_file:
        json.dump(dic, make_file, indent="\t")

def SortRanking(currentSeason):
    with open('./content/lol-esports-3080c_data.json', 'r', encoding='UTF8') as file:
         json_data = json.load(file)

    with open('./content/2019Json2.json', 'r', encoding='UTF8') as file:
         Load_json_data = json.load(file)

    userdata = json_data['users']
    names = json_data['Ranking']
    items = names.items()
    res = sorted(items, reverse=True, key=lambda item: int(item[1]))
    json_ranker = dict(res)
    
    # 정렬한 것을 토대로 값을 변경한다
    dic = {}
    rank = 1
    for ranker in json_ranker:
        if 'matchData' in userdata[ranker]:
            # 보상 최소 조건 10판, 실버부터?
            row = userdata[ranker]['matchData'].split(',')
            if int(row[0]) >= 10:
                if json_ranker[ranker] >= 100:
                    if 'curretSeason' in userdata[ranker]:
                        if currentSeason == userdata[ranker]['curretSeason']:
                            row = userdata[ranker]['matchData'].split(',')
                            value = str(json_ranker[ranker]) + ',' + row[0] + ',' + row[1] + ',' + str(rank) + ',' + str(False)
                            if 'ranker' in Load_json_data:
                                Load_json_data[ranker][currentSeason] = value
                            else:
                                Load_json_data[ranker] = {currentSeason : value}
                            rank +=1
                    else:
                        if currentSeason == 202000:
                            row = userdata[ranker]['matchData'].split(',')
                            value = str(json_ranker[ranker]) + ',' + row[0] + ',' + row[1] + ',' + str(rank) + ',' + str(False)
                            # 선수가 기존에 있는지
                            if ranker in Load_json_data:
                                Load_json_data[ranker][currentSeason] = value
                            else:
                                Load_json_data[ranker] = {currentSeason : value}
                            rank +=1
    
    with open('./content/rakingJson.json', 'w', encoding='utf-8') as make_file:
        json.dump(Load_json_data, make_file, indent="\t")

def SeasonData(originData):
    userdata = originData['users']
    names = originData['Ranking']
    Load_json_data = originData['SeasonDatas']
    items = names.items()
    res = sorted(items, reverse=True, key=lambda item: int(item[1]))
    json_ranker = dict(res)
    
    # 정렬한 것을 토대로 값을 변경한다
    dic = {}
    rank = 1
    for ranker in json_ranker:
        if 'matchData' in userdata[ranker]:
            # 보상 최소 조건 10판, 실버부터?
            row = userdata[ranker]['matchData'].split(',')
            if int(row[0]) >= 10:
                if json_ranker[ranker] >= 100:
                    if 'curretSeason' in userdata[ranker]:
                        if currentSeason == userdata[ranker]['curretSeason']:
                            row = userdata[ranker]['matchData'].split(',')
                            value = str(json_ranker[ranker]) + ',' + row[0] + ',' + row[1] + ',' + str(rank) + ',' + str(False)
                            if 'ranker' in Load_json_data:
                                Load_json_data[ranker][currentSeason] = value
                            else:
                                Load_json_data[ranker] = {currentSeason : value}
                            rank +=1
                    else:
                        if currentSeason == 202000:
                            row = userdata[ranker]['matchData'].split(',')
                            value = str(json_ranker[ranker]) + ',' + row[0] + ',' + row[1] + ',' + str(rank) + ',' + str(False)
                            # 선수가 기존에 있는지
                            if ranker in Load_json_data:
                                Load_json_data[ranker][currentSeason] = value
                            else:
                                Load_json_data[ranker] = {currentSeason : value}
                            rank +=1

def Edit2019Season():
    with open('./content/lol-esports-3080c_data.json', 'r', encoding='UTF8') as file:
         json_data = json.load(file)

    userdata = json_data['users']

    dic = {}
    for user in userdata:
        if 'SeasonDatas' in userdata[user]:
            value = userdata[user]['SeasonDatas']['2019']
            dic[user] = value

    with open('./content/2019Json.json', 'w', encoding='utf-8') as make_file:
        json.dump(dic, make_file, indent="\t")

def Edit2019Season2():
    with open('./content/2019Json.json', 'r', encoding='UTF8') as file:
         json_data = json.load(file)

    dic = {}
    for user in json_data:
        json_data[user] = {201900: json_data[user]}

    with open('./content/2019Json2.json', 'w', encoding='utf-8') as make_file:
        json.dump(json_data, make_file, indent="\t")

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

def DFJsonLoad():
    data_df = pd.read_json("C:/ooo.json", lines=True)
    return data_df

def DFJsonSave(data_df):
    data_df.to_json('test.json', orient='table')

def SeasonJson():
    with open('./lol-esports-3080c_data.json', 'r', encoding='UTF8') as file:
        json_data = json.load(file)
    
    rankdata = json_data['Ranking']
    matchdata = json_data['MatchDatas']
    userdata = json_data['users']
    seasondata = json_data['SeasonDatas']
    teamName = json_data['TeamName']

    # 정렬
    res = sorted(rankdata.items(), reverse=True, key=lambda item: int(item[1]))
    json_ranker = dict(res)
    
    with open('./Backup/rank.json', 'w', encoding='utf-8') as make_file:
        json.dump(json_ranker, make_file, indent="\t")


def Years():
    # 현재 날짜 확인
    todayDate = datetime.today()
    todayDate = todayDate.utcnow()

    cred = credentials.Certificate("lol-esports-3080c-firebase-adminsdk-80b6e-851af7998b.json")
    firebase_admin.initialize_app(cred,{
        'databaseURL' : "https://lol-esports-3080c.firebaseio.com/"
    })

    delUsers = []
    
    page = auth.list_users()
    while page:
        for user in page.users:
            login = str(user.user_metadata.last_sign_in_timestamp)[:10]
            loginDate = datetime.utcfromtimestamp(int(login))
            vsDate = todayDate - loginDate
            # 3년 이상이면
            if vsDate.days >= 1095:
                delUsers.append([user.uid, loginDate])

        page = page.get_next_page()

    backupPd = pd.DataFrame(data=delUsers, columns=["uid", 'loginDate'])
    backupPd.to_csv('./User3Years.csv', mode='w', index=False, encoding='utf-8-sig')
    
def DelYears():
    backupPd = pd.read_csv('./User3Years.csv', encoding='utf-8-sig')

    cred = credentials.Certificate("lol-esports-3080c-firebase-adminsdk-80b6e-851af7998b.json")
    firebase_admin.initialize_app(cred,{
        'databaseURL' : "https://lol-esports-3080c.firebaseio.com/"
    })

    dir = db.reference()

    for id in tqdm(backupPd['uid']):
        try:
            auth.delete_user(id)
        except:
            print("유저 없음: " + id)
        dir.child('users/').child(id).delete()

Export(202401, False)
#FirebaseSeason(202301)


#Years()
#DelYears()