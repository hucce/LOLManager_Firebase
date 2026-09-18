import json
import os
from pickle import FALSE
from time import sleep
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
from firebase_admin import auth
import pandas as pd
from datetime import datetime, timezone
from tqdm import tqdm



def _init_firebase_app():
    """Initialize Firebase Admin app once.

    firebase_admin.initialize_app()는 프로세스당 1회만 가능하므로,
    이미 초기화된 경우에는 기존 앱을 재사용한다.
    """
    try:
        firebase_admin.get_app()
        return
    except ValueError:
        pass

    cred = credentials.Certificate("lol-esports-3080c-firebase-adminsdk-80b6e-851af7998b.json")
    firebase_admin.initialize_app(
        cred,
        {
            'databaseURL': "https://lol-esports-3080c.firebaseio.com/"
        },
    )


def _normalize_dict_keys_to_str(value):
    """Firebase Realtime DB는 key가 문자열로 저장되므로 비교를 위해 key를 문자열로 정규화한다."""
    if isinstance(value, dict):
        normalized = {}
        for k, v in value.items():
            normalized[str(k)] = _normalize_dict_keys_to_str(v)
        return normalized
    if isinstance(value, list):
        return [_normalize_dict_keys_to_str(v) for v in value]
    return value


def _dict_is_subset(expected, actual):
    """actual이 expected를 (재귀적으로) 포함하면 True.

    - update()는 기존 데이터를 '병합'하므로 서버에 추가 키가 있어도 정상 케이스로 처리한다.
    """
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        for k, expected_v in expected.items():
            if k not in actual:
                return False
            if not _dict_is_subset(expected_v, actual[k]):
                return False
        return True
    if isinstance(expected, list):
        # 리스트는 순서/길이 이슈가 많아 기본 비교만 수행
        return expected == actual
    return expected == actual


def _write_and_verify(dir_ref, child_path, data, method='update', exact=False, retries=3, delay_seconds=1.5, verbose_label=None):
    """Firebase RTDB에 쓰기 후, get으로 재조회해서 반영 여부를 확인한다.

    - method: 'update' | 'set'
      - update: 병합(기존 키 유지)
      - set: 완전 덮어쓰기(기존 키 제거)
    - exact:
      - True면 서버 값이 기대값과 '완전 동일'해야 성공
      - False면 서버 값이 기대값을 '포함'하면 성공(병합 업데이트에 적합)
    """
    normalized_data = _normalize_dict_keys_to_str(data)
    label = verbose_label or child_path

    last_actual = None
    for attempt in range(1, retries + 1):
        if method == 'set':
            dir_ref.child(child_path).set(normalized_data)
        else:
            dir_ref.child(child_path).update(normalized_data)

        sleep(delay_seconds)

        last_actual = dir_ref.child(child_path).get() or {}
        last_actual = _normalize_dict_keys_to_str(last_actual)

        ok = (normalized_data == last_actual) if exact else _dict_is_subset(normalized_data, last_actual)
        if ok:
            print(f"{label} 업데이트 검증 성공 (시도 {attempt}/{retries}, method={method}, exact={exact})")
            return True

        print(f"{label} 업데이트 검증 실패 (시도 {attempt}/{retries}, method={method}, exact={exact})")
        sleep(delay_seconds)

    print(f"{label} 업데이트 최종 실패: 서버 반영이 확인되지 않았습니다.")
    return False


def _write_job_marker_and_verify(dir_ref, currentSeason, retries=3, delay_seconds=1.0):
    """트래픽을 최소화하기 위해, 대용량 데이터 자체를 재조회하지 않고 작은 마커만 써서 업로드 성공 여부를 확인한다."""
    run_id = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
    marker_path = 'AdminJobs/ExportRun'
    marker_payload = {
        'runId': run_id,
        'season': str(currentSeason),
        'utc': datetime.utcnow().isoformat(),
    }

    ok = _write_and_verify(
        dir_ref,
        marker_path,
        marker_payload,
        method='update',
        exact=False,
        retries=retries,
        delay_seconds=delay_seconds,
        verbose_label='AdminJobs/ExportRun',
    )

    if ok:
        # runId가 서버에 반영됐는지 한 번 더 확인(매우 작은 get)
        server_run_id = dir_ref.child(marker_path).child('runId').get()
        if server_run_id == run_id:
            print('업로드 마커 검증 성공')
            return True
        print('업로드 마커 검증 실패: runId 불일치')
    return False

def FirebaseSeason(currentSeason):
    currentSeason = str(currentSeason)
    cred = credentials.Certificate("lol-esports-3080c-firebase-adminsdk-80b6e-851af7998b.json")
    firebase_admin.initialize_app(cred,{
        'databaseURL' : "https://lol-esports-3080c.firebaseio.com/"
    })
    dir = db.reference()

    json_data = dir.get()
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

    WriteTop10MatchTeams(json_ranker, userdata, teamName, matchdata)

    # 업데이트
    dir.child('MatchDatas').update(matchDic)
    dir.child('Ranking').update(rankDic)
    dir.child('SeasonDatas').update(seasondata)

def Export(currentSeason, serverUP):
    currentSeason = str(currentSeason)
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
        _init_firebase_app()
        dir = db.reference()

        # 업데이트 (트래픽 최소화를 위해 대용량 노드 재조회/샘플 검증은 하지 않음)
        print('매치데이터 서버 업로드')
        dir.child('MatchDatas').update(matchDic)
        sleep(2)

        print('시즌 서버 업로드')
        dir.child('SeasonDatas').update(seasondata)
        sleep(2)

        print('랭킹 서버 업로드')
        dir.child('Ranking').update(rankDic)
        sleep(2)

        # 아주 작은 마커만 업데이트/재조회해서 서버 반영 여부 확인(트래픽 매우 적음)
        _write_job_marker_and_verify(dir, currentSeason, retries=3, delay_seconds=1.0)

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
    # 현재 UTC 날짜 확인
    todayDate = datetime.now(timezone.utc)

    _init_firebase_app()

    delUsers = []
    total_scanned = 0

    print("Firebase Auth 유저 목록 조회 시작...")
    page = auth.list_users()
    while page:
        for user in page.users:
            total_scanned += 1
            meta = user.user_metadata
            last_sign_in_ms = meta.last_sign_in_timestamp
            creation_ms = meta.creation_timestamp

            # 마지막 로그인 시각이 있으면 사용, 없으면 가입일 사용
            if last_sign_in_ms:
                active_date = datetime.fromtimestamp(last_sign_in_ms / 1000.0, tz=timezone.utc)
                date_type = "last_login"
            elif creation_ms:
                active_date = datetime.fromtimestamp(creation_ms / 1000.0, tz=timezone.utc)
                date_type = "created"
            else:
                continue

            vsDate = todayDate - active_date
            # 3년(1095일) 이상 경과
            if vsDate.days >= 1095:
                delUsers.append({
                    "uid": user.uid,
                    "lastActiveDate": active_date.strftime("%Y-%m-%d %H:%M:%S"),
                    "dateType": date_type,
                    "daysInactive": vsDate.days
                })

        print(f"조회 진행 중... 현재까지 스캔된 유저: {total_scanned}명, 3년 이상 미접속: {len(delUsers)}명")
        page = page.get_next_page()

    backupPd = pd.DataFrame(delUsers)
    backupPd.to_csv('./User3Years.csv', mode='w', index=False, encoding='utf-8-sig')
    print(f"\n[완료] 총 {total_scanned}명 중 3년 이상 미접속 유저 {len(delUsers)}명을 './User3Years.csv'에 저장했습니다.")
    return backupPd


def BackupTargetUsers(uids):
    """삭제 대상 유저들의 DB 데이터(users, Ranking, MatchDatas, TeamName)를 로컬 JSON 파일로 백업합니다 (SeasonDatas는 제외/보존)."""
    _init_firebase_app()
    dir_ref = db.reference()

    uids_set = set(uids)
    print(f"\n[데이터 백업] 대상 유저 {len(uids_set)}명의 DB 데이터 백업을 시작합니다...")

    os.makedirs('./Backup', exist_ok=True)

    backup_data = {
        "backup_time": datetime.now(timezone.utc).isoformat(),
        "total_target_users": len(uids_set),
        "users": {},
        "Ranking": {},
        "MatchDatas": {},
        "TeamName": {}
    }

    nodes = ['users', 'Ranking', 'MatchDatas', 'TeamName']
    for node_name in nodes:
        print(f"  - [{node_name}] 노드 데이터 가져오는 중...")
        try:
            node_data = dir_ref.child(node_name).get() or {}
            matched = {k: v for k, v in node_data.items() if k in uids_set}
            backup_data[node_name] = matched
            print(f"    -> [{node_name}] {len(matched)}건 수집 완료")
        except Exception as e:
            print(f"    -> [{node_name}] 수집 중 오류: {e}")

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"./Backup/backup_3years_deleted_{timestamp_str}.json"
    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, ensure_ascii=False, indent=2)

    file_size_kb = os.path.getsize(backup_file) / 1024.0
    print(f"[백업 완료] 저장 경로: {backup_file} ({file_size_kb:.2f} KB)")
    return backup_file


def DelYears(skip_backup=False):
    if not os.path.exists('./User3Years.csv'):
        print("삭제 대상 파일 './User3Years.csv'가 없습니다. 먼저 Years()를 실행하세요.")
        return

    backupPd = pd.read_csv('./User3Years.csv', encoding='utf-8-sig')
    uids = backupPd['uid'].dropna().astype(str).tolist()
    total = len(uids)
    print(f"\n[삭제 작업 준비] './User3Years.csv'에서 {total}명의 대상 유저를 불러왔습니다.")

    if total == 0:
        print("삭제할 대상 유저가 없습니다.")
        return

    _init_firebase_app()
    dir_ref = db.reference()

    # 1. 삭제 전 로컬 백업
    if not skip_backup:
        BackupTargetUsers(uids)
    else:
        print("[주의] 백업을 건너뛰고 바로 삭제를 진행합니다.")

    # 2. Firebase Auth 일괄 삭제 (배치: 최대 1,000개)
    print(f"\n[1/2] Firebase Auth 계정 삭제 시작 (총 {total}명)...")
    auth_chunk_size = 1000
    auth_deleted_count = 0
    auth_errors_count = 0

    for i in tqdm(range(0, total, auth_chunk_size), desc="Auth Batch Delete"):
        chunk = uids[i:i + auth_chunk_size]
        try:
            result = auth.delete_users(chunk)
            auth_deleted_count += result.success_count
            auth_errors_count += result.failure_count
        except Exception as e:
            print(f"Auth 일괄 삭제 오류 ({i}~{i+len(chunk)}): {e}")

    print(f"  -> Firebase Auth 삭제 완료 (성공: {auth_deleted_count}건, 미존재/실패: {auth_errors_count}건)")

    # 3. Firebase RTDB 일괄 삭제 (SeasonDatas는 제외/보존, users/Ranking/MatchDatas/TeamName 삭제)
    print(f"\n[2/2] Firebase RTDB 데이터 삭제 시작 (SeasonDatas 제외 보존)...")
    db_chunk_size = 500
    for i in tqdm(range(0, total, db_chunk_size), desc="RTDB Multi-path Delete"):
        chunk = uids[i:i + db_chunk_size]
        updates = {}
        for uid in chunk:
            updates[f"users/{uid}"] = None
            updates[f"Ranking/{uid}"] = None
            updates[f"MatchDatas/{uid}"] = None
            updates[f"TeamName/{uid}"] = None

        try:
            dir_ref.update(updates)
        except Exception as e:
            print(f"RTDB 일괄 삭제 오류 ({i}~{i+len(chunk)}): {e}")

    print("\n[완료] 3년 이상 미접속 유저 삭제 작업이 모두 성공적으로 완료되었습니다!")


if __name__ == '__main__':
    # 위험: 실제 운영 DB 덮어쓰기 방지를 위해 주석 처리 유지
    # Export(202503, True)

    # 1. 3년 이상 미접속 유저 조회 및 CSV 저장
    Years()

    # 2. 데이터 백업 및 삭제 진행
    DelYears()