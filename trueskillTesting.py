import requests
import itertools
import math
from trueskill import Rating, rate, rate_1vs1, BETA, global_env

# S-NE Championship sku: RE-VRC-17-4151
#NZ Nationals: RE-VRC-17-4422
# North Texas Regionals: RE-VRC-17-3012
# Kansas:RE-VRC-17-4564
# Ohio: RE-VRC-17-3589
# North NY: RE-VRC-17-2871
# DelMarVa: RE-VRC-18-4291
# Pennsulvania: RE-VRC-17-4533
sku = 'RE-VRC-18-4291'

# define win probability method from trueskill.org documentation
def win_probability(team1, team2):
    delta_mu = sum(r.mu for r in team1) - sum(r.mu for r in team2)
    sum_sigma = sum(r.sigma ** 2 for r in itertools.chain(team1, team2))
    size = len(team1) + len(team2)
    denom = math.sqrt(size * (BETA * BETA) + sum_sigma)
    ts = global_env()
    return ts.cdf(delta_mu / denom)

using_combined_rank = 1
using_ts_ccwm = 0
using_ccwm = 1
using_ts = 1
using_rank = 1
using_ap = 1
using_red = 0

# get ccwm or rank, as appropriate
url = "https://api.vexdb.io/v1/get_rankings"
params = {'sku':sku}
call = requests.get(url,params).json()
minCCWM = 100000
maxCCWM = 0
teamCCWM = {}
teamRank = {}
teamAp = {}
if using_ts_ccwm or using_ccwm:
    for teamIndex in xrange(call['size']):
        currentCCWM = call['result'][teamIndex]['ccwm']
        teamCCWM[call['result'][teamIndex]['team']] = currentCCWM #* (1.01 ** call['result'][teamIndex]['trsp'])
        if currentCCWM > maxCCWM:
            maxCCWM = currentCCWM
        if currentCCWM < minCCWM:
            minCCWM = currentCCWM
if using_rank:
    for teamIndex in xrange(call['size']):
        currentRank = call['result'][teamIndex]['rank']
        teamRank[call['result'][teamIndex]['team']] = currentRank
if using_ap:
    for teamIndex in xrange(call['size']):
        currentAp = call['result'][teamIndex]['ap']
        teamAp[call['result'][teamIndex]['team']] = currentAp

# find matches
url = "https://api.vexdb.io/v1/get_matches"
params = {'sku':sku,'round':'2'}
call = requests.get(url,params).json()
numMatches = call['size']
matches = call['result']
print numMatches

# find teams
url = "https://api.vexdb.io/v1/get_teams"
params = {'sku':sku}
call = requests.get(url,params).json()
initialTeamList = call['result']

# initialize rating for all teams
teams = {}
aTeamToTrack = ''
numMatchesPerTeam = 0
for result in initialTeamList:
    try:
        teamName = result['number']
        if using_ts_ccwm:
            startingSigma = (teamCCWM[teamName] - minCCWM)/maxCCWM * 50 + 0
            teams[teamName] = Rating(startingSigma,50/3)
        else:
            teams[teamName] = Rating()

        if aTeamToTrack == '':
            aTeamToTrack = teamName
    except:
        print 'err'
        # pass
print teams
# traverse through matches and update trueskill
if using_ts or using_ts_ccwm:
    num_iterations = 1
else:
    num_iterations = 0

for _ in xrange(num_iterations): #iterate trueskill 1 time if applicable
    for match in matches:
        # Increment matches per team if applicable
        if aTeamToTrack in [match['red1'],match['red2'],match['blue1'],match['blue2']]:
            numMatchesPerTeam += 1

        # declare teams
        r1 = teams[match['red1']]
        r2 = teams[match['red2']]
        b1 = teams[match['blue1']]
        b2 = teams[match['blue2']]

        # find winner
        if match['redscore'] > match['bluescore']:
            redRank = 0
            blueRank = 1
        elif match['redscore'] < match['bluescore']:
            redRank = 1
            blueRank = 0
        else:
            redRank = 0
            blueRank = 0

        # calculate new trueskill values
        (new_r1, new_r2), (new_b1, new_b2) = rate([[r1, r2],[b1, b2]], ranks=[redRank,blueRank])

        teams[match['red1']] = new_r1
        teams[match['red2']] = new_r2
        teams[match['blue1']] = new_b1
        teams[match['blue2']] = new_b2

print "Matches per team:", numMatchesPerTeam
# for team, skill in reversed(sorted(teams.iteritems(), key=lambda (k,v): (v,k))):
    # print team + ": " + str(skill.mu) + ", " + str(skill.sigma)

# calculate final rank
if using_combined_rank:
    team_combined_ranks = {}
    if using_ts:
        maxTS = max(teams.values())
        minTS = min(teams.values())
    if using_ccwm:
        maxCCWM = max(teamCCWM.values())
        minCCWM = min(teamCCWM.values())
    if using_rank:
        lowestRank = max(teamRank.values())
    if using_ap:
        maxAp = max(teamAp.values())
        minAp = min(teamAp.values())

    for team in teamCCWM.keys():
        combined_rank = 0
        if using_ts:
            combined_rank += (teams[team].mu*1.0 - minTS.mu)/maxTS.mu * 50
        if using_ccwm:
            combined_rank += (teamCCWM[team]*1.0 - minCCWM)/maxCCWM * 50
        if using_rank:
            combined_rank += (lowestRank - teamRank[team]*1.0)/lowestRank * 50
        if using_ap:
            combined_rank += (teamAp[team]*1.0 - minAp)/maxAp * 50

        team_combined_ranks[team] = combined_rank
print minAp
print maxAp
print teamAp
print team_combined_ranks
# check correctness against elimination matches
print ('getting to elimMatches')
correctPredictions = 0
incorrectPredictions = 0
ties = 0
for round in xrange(3,6): #for each of QF, SF, and F
    # get matches
    url = "https://api.vexdb.io/v1/get_matches"
    params = {'sku':sku,'round':round}
    call = requests.get(url,params).json()
    elimMatches = call['result']

    # check each match for correctness
    for match in elimMatches:
        # set up teams
        redTeams = [match['red1'],match['red2'],match['red3']]
        redTeams.remove(match['redsit'])
        blueTeams = [match['blue1'],match['blue2'],match['blue3']]
        blueTeams.remove(match['bluesit'])
        redRanking = [teams[redTeams[0]], teams[redTeams[1]]]
        blueRanking = [teams[blueTeams[0]], teams[blueTeams[1]]]

        # determine victory
        tie = 0
        tieResultToPrint = ''
        if using_combined_rank:
            expected = 1 if team_combined_ranks[redTeams[0]] + team_combined_ranks[redTeams[1]] > team_combined_ranks[blueTeams[0]] + team_combined_ranks[blueTeams[1]] else 0
            tie = 1 if abs((team_combined_ranks[redTeams[0]] + team_combined_ranks[redTeams[1]]) - (team_combined_ranks[blueTeams[0]] + team_combined_ranks[blueTeams[1]])) < 10 else 0
            tieResultToPrint = str(team_combined_ranks[redTeams[0]] + team_combined_ranks[redTeams[1]]) + " : " + str(team_combined_ranks[blueTeams[0]] + team_combined_ranks[blueTeams[1]])
        elif using_ts or using_ts_ccwm:
            expected = 1 if win_probability(redRanking,blueRanking)>0.5 else 0
            tie = 1 if 0.4 < win_probability(redRanking,blueRanking) < 0.6 else 0
            tieResultToPrint = str(win_probability(redRanking,blueRanking))
        elif using_ccwm:
            expected = 1 if teamCCWM[redTeams[0]] + teamCCWM[redTeams[1]] > teamCCWM[blueTeams[0]] + teamCCWM[blueTeams[1]] else 0
            tie = 1 if abs((teamCCWM[redTeams[0]] + teamCCWM[redTeams[1]]) - (teamCCWM[blueTeams[0]] + teamCCWM[blueTeams[1]])) < 5 else 0
            tieResultToPrint = str(teamCCWM[redTeams[0]] + teamCCWM[redTeams[1]]), ":", str(teamCCWM[blueTeams[0]] + teamCCWM[blueTeams[1]])
        elif using_rank:
            expected = 1 if teamRank[redTeams[0]] + teamRank[redTeams[1]] < teamRank[blueTeams[0]] + teamRank[blueTeams[1]] else 0
            tie = 1 if abs((teamRank[redTeams[0]] + teamRank[redTeams[1]]) - (teamRank[blueTeams[0]] + teamRank[blueTeams[1]])) < 5 else 0
            tieResultToPrint = str(teamRank[redTeams[0]] + teamRank[redTeams[1]]), ":", str(teamRank[blueTeams[0]] + teamRank[blueTeams[1]])
        elif using_ap:
            expected = 1 if teamAp[redTeams[0]] + teamAp[redTeams[1]] > teamAp[blueTeams[0]] + teamAp[blueTeams[1]] else 0
            tie = 1 if abs((teamAp[redTeams[0]] + teamAp[redTeams[1]]) - (teamAp[blueTeams[0]] + teamAp[blueTeams[1]])) < 5 else 0
            tieResultToPrint = str(teamAp[redTeams[0]] + teamAp[redTeams[1]]), ":", str(teamAp[blueTeams[0]] + teamAp[blueTeams[1]])
        elif using_red:
            expected = 1
        actual = 1 if match['redscore']>match['bluescore'] else 0

        # collect results
        if tie:
            ties += 1
            print tieResultToPrint
        elif(expected==actual):
            correctPredictions += 1
            # print(win_probability(redRanking,blueRanking))
        else:
            incorrectPredictions +=1
            print "\'",match['round'],"-",match['instance'],"-",match['matchnum']
            # print(redTeams, blueTeams, win_probability(redRanking,blueRanking))

print 'Correct:', correctPredictions
print 'Incorrect:', incorrectPredictions
print 'Ties:', ties

# print(win_probability([teams['2442C'],teams['4478V']], [teams['81118P'],teams['4478X']]))
