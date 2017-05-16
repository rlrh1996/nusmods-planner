import requests
from stopwatch import *
from sets import Set
import json
from z3 import *
import mod_utils

# returns list of hours corresponding to day of the week for even and odd week
def freeDay(x):
	day = range(x*24,(x+1)*24)
	return day + [i+120 for i in day]
# returns selection: list of all lesson slots for us to iterate through the model to find schedule

def parseZ3Query(mods, numToTake, solver = Solver()):
    timetable = [] # contains the symbolic work hours for all mods
    selection = [] # represents all the lecture, rec slots etc
    numMods = len(mods)

    # numMods choose numToTake
    # creates indicators determining which modules we try
    X = [Int("x_%s" % i) for i in range(numToTake)]
    # assert that mods are distinct and have legal indices
    solver.add(Distinct(X))
    solver.add([And(X[i] >= 0, X[i]<numMods) for i in range(numToTake)])

    for modIndex, mod in enumerate(mods):
        moduleCode = mod[0]
        constraints = []
        selected = Or([X[i] == modIndex for i in range(numToTake)]) # is this mod selected

        # iterate through all timeslots and parse the implications
        # Each hours of the timeslot is represented as one z3 IntSort
        for lessonType, slots in mod[1].iteritems():
            firstFlag = True
            slotSelectors = [] # selector variable for timeslot
            for slotName, timing in slots.iteritems():
                if firstFlag:
                    timetable += [Int('%s_%s_%s' % (moduleCode, lessonType, index))
                                  for index in range(len(timing))]
                    firstFlag = False
                selector = Bool('%s_%s_%s' % (moduleCode, lessonType, slotName))
                selection.append(selector)
                slotSelectors.append(selector)
                # add implications if particular timeslot is selected
                for index, time in enumerate(timing):
                    # it is fine to repeat variable names, z3 maps to the same variable
                    implicants = [Int('%s_%s_%s' % (moduleCode, lessonType, index)) == time]
                    implication = Implies(selector, And(implicants))
                    constraints.append(implication)
            # pick one timeslot from each timeslot, or ignore if mod is not chosen
            constraints.append(Or(Or(slotSelectors),Not(selected)))
        # not selected then we don't care, tutorial for a mod we don't choose can be at -1945024 hrs
        solver.add(constraints)
    solver.add(Or([Distinct(timetable+freeDay(i)) for i in range(5)]))
    return selection

def timetablePlanner(modsstr, numToTake):
    def transformMod(modtuple):
        return (modtuple[0], splitIntoLessonTypes(modtuple[1]))
    s = Solver()
    mods = [mod_utils.queryAndTransform(m) for m in modsstr]
    selection = parseZ3Query(mods, numToTake, s)
    if s.check() == sat:
        m = s.model()
        schedule = [str(s) for s in selection if m[s]]
        return schedule

# code for travel minimisation goes here

def parseZ3QueryMinTravel(mods, numToTake, solver = Solver()):
    timetable = [] # contains the symbolic work hours for all mods
    selection = [] # represents all the lecture, rec slots etc
    numMods = len(mods)

    # numMods choose numToTake
    # creates indicators determining which modules we try
    X = [Int("x_%s" % i) for i in range(numToTake)]
    # assert that mods are distinct and have legal indices
    solver.add(Distinct(X))
    solver.add([And(X[i] >= 0, X[i]<numMods) for i in range(numToTake)])

    for modIndex, mod in enumerate(mods):
        moduleCode = mod[0]
        constraints = []
        selected = Or([X[i] == modIndex for i in range(numToTake)]) # is this mod selected

        # iterate through all timeslots and parse the implications
        # Each hours of the timeslot is represented as one z3 IntSort
        for lessonType, slots in mod[1].iteritems():
            firstFlag = True
            slotSelectors = [] # selector variable for timeslot
            for slotName, timing in slots.iteritems():
                if firstFlag:
                    timetable += [Int('%s_%s_%s' % (moduleCode, lessonType, index))
                                  for index in range(len(timing))]
                    firstFlag = False
                selector = Bool('%s_%s_%s' % (moduleCode, lessonType, slotName))
                selection.append(selector)
                slotSelectors.append(selector)
                # add implications if particular timeslot is selected
                for index, time in enumerate(timing):
                    # it is fine to repeat variable names, z3 maps to the same variable
                    implicants = [Int('%s_%s_%s' % (moduleCode, lessonType, index)) == time]
                    implication = Implies(selector, And(implicants))
                    constraints.append(implication)
            # pick one timeslot from each timeslot, or ignore if mod is not chosen
            constraints.append(Or(Or(slotSelectors),Not(selected)))
        # not selected then we don't care, tutorial for a mod we don't choose can be at -1945024 hrs
        solver.add(constraints)
    
    return selection

def run():
    t = Timer()
    t.start()
    s = timetablePlanner(['cs1010', 'st2131', 'cs1231', 'ma1101r','cs2020','cs1020','cs2010'], 5)
    for i in s:
        print i
    print mod_utils.gotFreeDay(s)
    print t.stop()
run()