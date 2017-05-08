import requests
from sets import Set
import json
from z3 import *

ENV = "DEV" # faster to do everything offline

# TO DO: no mod is present in both compmods and optmods, and all module codes are valid (i.e. safeguard against dumb user input)

# ModuleCode -> [Lessons]

## Helper functions
if ENV == "DEV":
    _mods = json.load(open('timetable.json'))
    _dict = {x['ModuleCode']: x['Timetable'] for x in _mods if 'Timetable' in x}

# modjson: json object
def splitIntoLessonTypes(mod):
    lessonTypes = Set([i['LessonType'] for i in mod])
    mydict = {}
    for i in lessonTypes:
    	mydict[i] = {}
    for lst in mod:
    	tList = timeList(lst["WeekText"], lst["DayText"], lst["StartTime"], lst["EndTime"])
    	classId = lst['ClassNo']
    	lType = lst['LessonType']
    	if classId in mydict[lType].keys():
    		mydict[lType][classId] = mydict[lType][classId] + tList
    	else:
    		mydict[lType][classId] = tList
    #dictionary(lessontype,dictionary(classNo, timeList))
    return mydict

# http://api.nusmods.com/2016-2017/1/modules/ST2131/timetable.json
# returns tuple of (ModuleCode, [{Lessons for each type}])
def query(code):
    code = code.upper() # codes are in upper case
    # if in DEV mode then pull everything from local sources
    if ENV == "DEV":
        #return _dict[code]
        return (code, _dict[code])
    # TODO test online API
    # might have broken the online one
	r = requests.get('http://api.nusmods.com/2016-2017/1/modules/' + code.upper() + '/timetable.json')
	r = r.json()
	return r

# returns free day constraint, x is a weekday from 0 to 4
def freeDay(x):
	day = range(x*24,(x+1)*24)
	return day + [i+120 for i in day]

# returns list of discrete timeslots based on hour-based indexing in a fortnight
# used for z3's distinct query. 0-119 first week, 120-239 second week.
def timeList(weektext, daytext, starttime, endtime):
    #some hard code
    weekdays = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 4}
    ofst = weekdays[daytext]*24
    lst = [i+ofst for i in range(int(starttime)/100, int(endtime)/100)]
    if (weektext == "Odd Week"):
        return lst
    elif (weektext == "Even Week"):
        return [i+120 for i in lst]
    # default every week
    else:
        return [i+120 for i in lst]+lst

def transformMod(modtuple):
    return (modtuple[0], splitIntoLessonTypes(modtuple[1]))

# list of (moduleCode, {transformedLessons}) tuples and returns imcomplete z3 query
def parseZ3Queryv2(compmods, optmods, numToTake, solver = Solver()):
    complen = len(compmods)
    if complen > numToTake:
    	dummy = Int('dummy')
    	solver.add([dummy<1,dummy>1]) #for unsat
    	return
    timetable = []
    selection = []
    mods = compmods + optmods
    numMods = len(mods)
    X = [Int("x_%s" % i) for i in range(numToTake)] # creates indicators determining which modules we try
    solver.add([X[i]==i for i in range(complen)])
    solver.add([X[i]<X[i+1] for i in range(numToTake-1)])
    solver.add(X[0] >= 0)
    solver.add(X[numToTake-1] < numMods)
    for modIndex, mod in enumerate(mods):
        moduleCode = mod[0]
        constraints = []
        selected = Or([X[i] == modIndex for i in range(numToTake)]) #is this mod selected
        for lessonType, slots in mod[1].iteritems():
            firstFlag = True
            slotSelectors = []
            for slotName, timing in slots.iteritems():
                if firstFlag:
                    # add to timetable
                    timetable += [Int('%s_%s_%s' % (moduleCode, lessonType, index))
                                  for index in range(len(timing))]
                    firstFlag = False
                selector = Bool('%s_%s_%s' % (moduleCode, lessonType[:3], slotName))
                constraints.append(Implies(selector,Or([modIndex == X[i] for i in range(numToTake)]))) 
                #small bug fix here to guarantee selector can only be true when we are taking that mod, otherwise solver could randomly fill up free slot
                selection.append(selector)
                slotSelectors.append(selector)
                for index, time in enumerate(timing):
                    implicants = [Int('%s_%s_%s' % (moduleCode, lessonType, index)) == time]
                    implication = Implies(selector, And(implicants))
                    constraints.append(implication)
            constraints.append(Or(Or(slotSelectors),Not(selected))) 
        # not selected then we don't care, tutorial for a mod we don't choose can be at -1945024 hrs
        # solver.add(Implies(selected, constraints))
        solver.add(constraints)
    # print timetable
    # want timetable to be distinct
    solver.add(Or([Distinct(timetable+freeDay(i)) for i in range(5)]))
    return selection

# old code, but I don't want to deal with versioning if we happen to need this in future - cleanup can be done after completion
def parseZ3Query(mods, numToTake, solver = Solver()):
    timetable = []
    selection = []
    numMods = len(mods)
    X = [Int("x_%s" % i) for i in range(numToTake)] # creates indicators determining which modules we try
    solver.add([X[i]<X[i+1] for i in range(numToTake-1)])
    solver.add(X[0] >= 0)
    solver.add(X[numToTake-1] < numMods)
    for modIndex, mod in enumerate(mods):
        moduleCode = mod[0]
        constraints = []
        selected = Or([X[i] == modIndex for i in range(numToTake)]) #is this mod selected
        for lessonType, slots in mod[1].iteritems():
            firstFlag = True
            slotSelectors = []
            for slotName, timing in slots.iteritems():
                if firstFlag:
                    # add to timetable
                    timetable += [Int('%s_%s_%s' % (moduleCode, lessonType, index))
                                  for index in range(len(timing))]
                    firstFlag = False
                selector = Bool('%s_%s_%s' % (moduleCode, lessonType[:3], slotName))
                constraints.append(Implies(selector,Or([modIndex == X[i] for i in range(numToTake)]))) 
                #small bug fix here to guarantee selector can only be true when we are taking that mod, otherwise solver could randomly fill up free slot
                selection.append(selector)
                slotSelectors.append(selector)
                for index, time in enumerate(timing):
                    implicants = [Int('%s_%s_%s' % (moduleCode, lessonType, index)) == time]
                    implication = Implies(selector, And(implicants))
                    constraints.append(implication)
            constraints.append(Or(Or(slotSelectors),Not(selected))) 
        # not selected then we don't care, tutorial for a mod we don't choose can be at -1945024 hrs
        # solver.add(Implies(selected, constraints))
        solver.add(constraints)
    # print timetable
    # want timetable to be distinct
    solver.add(Or([Distinct(timetable+freeDay(i)) for i in range(5)]))
    return selection

# old code
def timetablePlanner(modsstr, numToTake = 5):
    s = Solver()
    mods = [transformMod(query(m)) for m in modsstr]
    selection = parseZ3Query(mods, numToTake, s)
    if s.check() == sat:
        print "Candidate:"
        m = s.model()
        print m
        for s in selection:
            if m[s]:
                print s
    else:
        print "free day not possible"

def timetablePlannerv2(compmodsstr, optmodsstr, numToTake):
    s = Solver()
    compmods = [transformMod(query(m)) for m in compmodsstr]
    optmods = [transformMod(query(m)) for m in optmodsstr]
    selection = parseZ3Queryv2(compmods, optmods, numToTake, s)
    if s.check() == sat:
        print "Candidate:"
        m = s.model()
        # print m
        for s in selection:
            if m[s]:
                print s
    else:
        print "free day not possible"

# insert unit tests here, should shift them to a separate file later
def run():
    mod = query('st2131')
    mod = transformMod(mod)
    # parseZ3Query([mod])

    print "Some tests"
    # timetablePlanner(['cs1010', 'st2131', 'cs1231', 'ma1101r','cs2020','cs1020','cs2010', 'cs3230','cs3233'], 5)
    # timetablePlannerv2([], ['cs1010', 'st2131', 'cs1231', 'ma1101r','cs2020','cs1020','cs2010', 'cs3230','cs3233'], 5)
    # timetablePlannerv2(['cs1010'], ['st2131', 'cs1231', 'ma1101r','cs2020','cs1020','cs2010', 'cs3230','cs3233'], 5)
    timetablePlannerv2(['cs1010','cs1020'], ['st2131', 'cs1231', 'ma1101r','cs2020','cs2010', 'cs3230','cs3233'], 4)
    # timetablePlannerv2(['cs1010','cs1020','st2131', 'cs1231', 'ma1101r'], ['cs2020','cs2010', 'cs3230','cs3233'], 4)
    # f = open('out.txt', 'w')
    # print >> f, splitIntoLessonTypes(json.load(open('st2131.json')))
    # f.close()
    #lessons = splitIntoLessonTypes(mod)
    #print lessons

    #print [Bool('b%s' % i) for i in range(5)]

    #print "\n\nPrinting Z3 bools"
    #parseZ3Query([lessons])

run()

