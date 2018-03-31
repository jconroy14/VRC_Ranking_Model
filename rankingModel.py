import itertools
import math
from trueskill import Rating, rate, rate_1vs1, BETA, global_env

# define win probability method from trueskill.org documentation
def win_probability(team1, team2):
    delta_mu = sum(r.mu for r in team1) - sum(r.mu for r in team2)
    sum_sigma = sum(r.sigma ** 2 for r in itertools.chain(team1, team2))
    size = len(team1) + len(team2)
    denom = math.sqrt(size * (BETA * BETA) + sum_sigma)
    ts = global_env()
    return ts.cdf(delta_mu / denom)

def getAccuracy(model,qualificationMatches,eliminationMatches,rankings,tieMargin):
    if len(qualificationMatches) + len(eliminationMatches) == 0:
        return '--'

    try:
        # INITIALIZATION OF VARIABLES
        # select model
        using_combined_rank = model[0]
        using_ts_ccwm = model[1]
        using_ccwm = model[2]
        using_ts = model[3]
        using_rank = model[4]
        using_ap = model[5]
        using_red = model[6]

        # Get team list from rankings
        teamList = []
        for teamIndex in xrange(rankings['size']):
            teamList.append(rankings['result'][teamIndex]['team'])
        # get ccwm, rank, and ap as appropriate
        teamCCWM = {}
        teamRank = {}
        teamAp = {}
        if using_ts_ccwm or using_ccwm:
            for teamIndex in xrange(rankings['size']):
                currentCCWM = rankings['result'][teamIndex]['ccwm']
                teamCCWM[rankings['result'][teamIndex]['team']] = currentCCWM #* (1.01 ** call['result'][teamIndex]['trsp'])
        if using_rank:
            for teamIndex in xrange(rankings['size']):
                currentRank = rankings['result'][teamIndex]['rank']
                teamRank[rankings['result'][teamIndex]['team']] = currentRank
        if using_ap:
            for teamIndex in xrange(rankings['size']):
                currentAp = rankings['result'][teamIndex]['ap']
                teamAp[rankings['result'][teamIndex]['team']] = currentAp

        # initialize rating for all teams
        teamTS = {}
        aTeamToTrack = ''
        numMatchesPerTeam = 0
        for teamName in teamList:
            if using_ts_ccwm:
                minCCWM = min(teamCCWM.values())
                maxCCWM = max(teamCCWM.values())
                try:
                    startingMu = (teamCCWM[teamName] - minCCWM)/maxCCWM * 50 + 0
                except:
                    startingMu = 25
                teamTS[teamName] = Rating(startingMu,50/3)
            else:
                teamTS[teamName] = Rating()

            if aTeamToTrack == '':
                aTeamToTrack = teamName

        # traverse through matches and update trueskill
        if using_ts or using_ts_ccwm:
            num_iterations = 1
        else:
            num_iterations = 0

        for _ in xrange(num_iterations): #iterate trueskill 1 time if applicable
            for match in qualificationMatches:
                # Increment matches per team if applicable
                if aTeamToTrack in [match['red1'],match['red2'],match['blue1'],match['blue2']]:
                    numMatchesPerTeam += 1

                # declare teams
                r1 = teamTS[match['red1']]
                r2 = teamTS[match['red2']]
                b1 = teamTS[match['blue1']]
                b2 = teamTS[match['blue2']]

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

                teamTS[match['red1']] = new_r1
                teamTS[match['red2']] = new_r2
                teamTS[match['blue1']] = new_b1
                teamTS[match['blue2']] = new_b2

        print "Matches per team:", numMatchesPerTeam

        # calculate final rank
        if using_combined_rank:
            team_combined_ranks = {}
            if using_ts:
                maxTS = max(teamTS.values())
                minTS = min(teamTS.values())
            if using_ccwm:
                maxCCWM = max(teamCCWM.values())
                minCCWM = min(teamCCWM.values())
            if using_rank:
                lowestRank = max(teamRank.values())
            if using_ap:
                maxAp = max(teamAp.values())
                minAp = min(teamAp.values())

            for team in teamList:
                combined_rank = 0
                if using_ts:
                    try:
                        combined_rank += (teamTS[team].mu*1.0 - minTS.mu)/(maxTS.mu-minTS.mu) * 50
                    except ZeroDivisionError:
                        pass
                if using_ccwm:
                    try:
                        combined_rank += (teamCCWM[team]*1.0 - minCCWM)/(maxCCWM-minCCWM) * 50
                    except ZeroDivisionError:
                        pass
                if using_rank:
                    try:
                        combined_rank += (lowestRank - teamRank[team]*1.0)/lowestRank * 50
                    except ZeroDivisionError:
                        pass
                if using_ap:
                    try:
                        combined_rank += (teamAp[team]*1.0 - minAp)/(maxAp-minAp) * 50
                    except ZeroDivisionError:
                        pass

                team_combined_ranks[team] = combined_rank

        # check correctness against elimination matches
        correctPredictions = 0
        incorrectPredictions = 0
        ties = 0
        # check each match for correctness
        for match in eliminationMatches:
            # set up teams
            redTeams = [match['red1'],match['red2'],match['red3']]
            redTeams.remove(match['redsit'])
            blueTeams = [match['blue1'],match['blue2'],match['blue3']]
            blueTeams.remove(match['bluesit'])
            redRanking = [teamTS[redTeams[0]], teamTS[redTeams[1]]]
            blueRanking = [teamTS[blueTeams[0]], teamTS[blueTeams[1]]]

            # determine victory
            tie = 0
            tieResultToPrint = ''
            if using_combined_rank:
                expected = 1 if team_combined_ranks[redTeams[0]] + team_combined_ranks[redTeams[1]] > team_combined_ranks[blueTeams[0]] + team_combined_ranks[blueTeams[1]] else 0
                tie = 1 if abs((team_combined_ranks[redTeams[0]] + team_combined_ranks[redTeams[1]]) - (team_combined_ranks[blueTeams[0]] + team_combined_ranks[blueTeams[1]])) < tieMargin else 0
                tieResultToPrint = str(team_combined_ranks[redTeams[0]] + team_combined_ranks[redTeams[1]]) + " : " + str(team_combined_ranks[blueTeams[0]] + team_combined_ranks[blueTeams[1]])
            elif using_ts or using_ts_ccwm:
                expected = 1 if win_probability(redRanking,blueRanking)>0.5 else 0
                tie = 1 if abs(win_probability(redRanking,blueRanking) - 0.5) < tieMargin else 0
                tieResultToPrint = str(win_probability(redRanking,blueRanking))
            elif using_ccwm:
                expected = 1 if teamCCWM[redTeams[0]] + teamCCWM[redTeams[1]] > teamCCWM[blueTeams[0]] + teamCCWM[blueTeams[1]] else 0
                tie = 1 if abs((teamCCWM[redTeams[0]] + teamCCWM[redTeams[1]]) - (teamCCWM[blueTeams[0]] + teamCCWM[blueTeams[1]])) < tieMargin else 0
                tieResultToPrint = str(teamCCWM[redTeams[0]] + teamCCWM[redTeams[1]]), ":", str(teamCCWM[blueTeams[0]] + teamCCWM[blueTeams[1]])
            elif using_rank:
                expected = 1 if teamRank[redTeams[0]] + teamRank[redTeams[1]] < teamRank[blueTeams[0]] + teamRank[blueTeams[1]] else 0
                tie = 1 if abs((teamRank[redTeams[0]] + teamRank[redTeams[1]]) - (teamRank[blueTeams[0]] + teamRank[blueTeams[1]])) < tieMargin else 0
                tieResultToPrint = str(teamRank[redTeams[0]] + teamRank[redTeams[1]]), ":", str(teamRank[blueTeams[0]] + teamRank[blueTeams[1]])
            elif using_ap:
                expected = 1 if teamAp[redTeams[0]] + teamAp[redTeams[1]] > teamAp[blueTeams[0]] + teamAp[blueTeams[1]] else 0
                tie = 1 if abs((teamAp[redTeams[0]] + teamAp[redTeams[1]]) - (teamAp[blueTeams[0]] + teamAp[blueTeams[1]])) < tieMargin else 0
                tieResultToPrint = str(teamAp[redTeams[0]] + teamAp[redTeams[1]]), ":", str(teamAp[blueTeams[0]] + teamAp[blueTeams[1]])
            elif using_red:
                expected = 1
            actual = 1 if match['redscore']>match['bluescore'] else 0

            # collect results
            if tie:
                ties += 1
                # print tieResultToPrint
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
        try:
            percentCorrect = correctPredictions*100.0/(incorrectPredictions+correctPredictions)
        except:
            percentCorrect = '-'
        return [numMatchesPerTeam,percentCorrect]
        # print(win_probability([teams['2442C'],teams['4478V']], [teams['81118P'],teams['4478X']]))
    except:
        return ['-','-']
