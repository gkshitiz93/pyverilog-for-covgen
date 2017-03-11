#-------------------------------------------------------------------------------
# visit.py
# 
# Basic classes for binding tree analysis
#
# Copyright (C) 2013, Shinya Takamaeda-Yamazaki
# License: Apache 2.0
#-------------------------------------------------------------------------------
from __future__ import absolute_import
from __future__ import print_function
import sys
import os
import re
import copy
import collections

import pyverilog
import pyverilog.utils.util as util
import pyverilog.utils.verror as verror
from pyverilog.utils.scope import ScopeLabel, ScopeChain
from pyverilog.vparser.ast import *

map_key   = lambda f,d: collections.OrderedDict([ (f(k),v) for k,v in d.items() ])
map_value = lambda f,d: collections.OrderedDict([ (k,f(v)) for k,v in d.items() ])

################################################################################
# Primitive list
################################################################################
primitives = {
    'and' : Uand,
    'nand': Unand,
    'or' : Uor,
    'nor' : Unor,
    'xor' : Uxor,
    'xnor' : Uxnor,
    'not' : Unot,
    'buf' : None
}

################################################################################
# Base Visitor
################################################################################
class NodeVisitor(object):
    def visit(self, node):
        method = 'visit_' + node.__class__.__name__
        visitor = getattr(self, method, self.generic_visit)
        return visitor(node)
    def generic_visit(self, node):
        for c in node.children():
            self.visit(c)

################################################################################
# Signal/Object Management Classes
################################################################################
class AlwaysInfo(object):
    def __init__(self, clock_name='', clock_edge=None, clock_bit=0,
                 reset_name='', reset_edge=None, reset_bit=0, senslist=()):
        self.clock_name = clock_name
        self.clock_edge = clock_edge
        self.clock_bit = clock_bit
        self.reset_name = reset_name
        self.reset_edge = reset_edge
        self.reset_bit = reset_bit
        self.senslist = senslist
    def getClockName(self):
        return self.clock_name
    def getClockEdge(self):
        return self.clock_edge
    def getClockBit(self):
        return self.clock_bit
    def getResetName(self):
        return self.reset_name
    def getResetEdge(self):
        return self.reset_edge
    def getResetBit(self):
        return self.reset_bit
    def isClockEdge(self):
        if self.clock_name != '' and self.clock_edge == 'posedge': return True
        if self.clock_name != '' and self.clock_edge == 'negedge': return True
        return False
    def isCombination(self):
        if self.clock_name is None: return True
        return False
    def isResetEdge(self):
        if self.reset_name != '' and self.reset_edge == 'posedge': return True
        if self.reset_name != '' and self.reset_edge == 'negedge': return True
        return False

################################################################################
class Label(object):
    def __init__(self, name):
        self.name = name
        self.cnt = 0
    def get(self):
        ret = self.name + str(self.cnt)
        self.inc()
        return ret
    def inc(self):
        self.cnt += 1

class Labels(object):
    def __init__(self):
        self.labels = {}
    def get(self, name):
        if not name in self.labels: self.labels[name] = Label(name)
        return self.labels[name].get()
    def inc(self, name):
        if not name in self.labels: self.labels[name] = Label(name)
        self.labels[name].inc()

################################################################################
class VariableTable(object):
    def __init__(self):
        self.dict = collections.OrderedDict()
    def add(self, name, var):
        if name in self.dict:
            self.dict[name] = self.dict[name] + (var, )
        else:
            self.dict[name] = (var, )
    def get(self, name):
        return self.dict[name]
    def has(self, name):
        return name in self.dict
    def update(self, table):
        self.dict.update(table)
    def getDict(self):
        return self.dict
        
class SignalTable(VariableTable): pass
class ConstTable(VariableTable): pass
class GenvarTable(VariableTable): pass

class Variables(object):
    def __init__(self):
        self.signal = SignalTable()
        self.const = ConstTable()
        self.genvar = GenvarTable()
    def addSignal(self, name, var):
        if self.const.has(name): return
        self.signal.add(name, var)
    def addConst(self, name, var):
        if self.const.has(name): return
        self.const.add(name, var)
    def addGenvar(self, name, var):
        if self.const.has(name): return
        self.genvar.add(name, var)
    def getSignal(self, name):
        return self.signal.get(name)
    def getConst(self, name):
        return self.const.get(name)
    def getGenvar(self, name):
        return self.genvar.get(name)
    def hasSignal(self, name):
        return self.signal.has(name)
    def hasConst(self, name):
        return self.const.has(name)
    def updateSignal(self, var):
        self.signal.update(var)
    def updateConst(self, var):
        self.const.update(var)
    def getSignals(self):
        return self.signal.getDict()
    def getConsts(self):
        return self.const.getDict()

################################################################################
class DefinitionInfo(object):
    def __init__(self, name, definition):
        self.name = name
        self.definition = definition
        self.variables = Variables()
        self.ioports = []
        self.params = []
    def addSignal(self, name, var):
        self.variables.addSignal(name, var)
    def addConst(self, name, var):
        self.variables.addConst(name, var)
    def addParamName(self, name):
        self.params.append(name)
    def addPort(self, port):
        self.ioports.append(port)
    def addPorts(self, ports):
        for p in ports:
            if isinstance(p, Ioport):
                self.ioports.append(p.first.name)
            else:
                self.ioports.append(p.name)
    def getSignals(self):
        return self.variables.getSignals()
    def getConsts(self):
        return self.variables.getConsts()
    def getDefinition(self):
        return self.definition
    def getIOPorts(self):
        return tuple(self.ioports)
    def getParamNames(self):
        return tuple(self.params)

class DefinitionInfoTable(object):
    def __init__(self):
        self.dict = collections.OrderedDict()
        self.current = None
    def addDefinition(self, name, definition):
        if name in self.dict:
            raise verror.DefinitionError('Already defined: %s' % name)
        self.dict[name] = DefinitionInfo(name, definition)
        self.current = name
    def setCurrent(self, name):
        self.current = name
    def addPorts(self, ports):
        self.dict[self.current].addPorts(ports)
    def addPort(self, port):
        self.dict[self.current].addPort(port)
    def addSignal(self, name, var):
        self.dict[self.current].addSignal(name, var)
    def addConst(self, name, var):
        self.dict[self.current].addConst(name, var)
    def addParamName(self, name):
        self.dict[self.current].addParamName(name)
    def getSignals(self, name):
        if name not in self.dict: raise verror.DefinitionError('No such module: %s' % name)
        return self.dict[name].getSignals()
    def getConsts(self, name):
        if name not in self.dict: raise verror.DefinitionError('No such module: %s' % name)
        return self.dict[name].getConsts()
    def getDefinition(self, name):
        if name not in self.dict: raise verror.DefinitionError('No such module: %s' % name)
        return self.dict[name].getDefinition()
    def getDefinitions(self):
        return self.dict
    def getIOPorts(self, name):
        if name not in self.dict: raise verror.DefinitionError('No such module: %s' % name)
        return self.dict[name].getIOPorts()
    def getParamNames(self, name):
        if name not in self.dict: raise verror.DefinitionError('No such module: %s' % name)
        return self.dict[name].getParamNames()
    def get_names(self):
        ret = []
        for dk, dv in self.dict.items():
            ret.append(dk)
        return ret
    def overwriteDefinition(self, name, definition):
        self.dict[name] = definition
    def copyDefinition(self, f, t):
        self.dict[t] = copy.deepcopy(self.dict[f])
        self.dict[t].definition.name = t
        self.dict[t].name = t

class FunctionInfo(DefinitionInfo): pass
class FunctionInfoTable(DefinitionInfoTable): pass
class TaskInfo(DefinitionInfo): pass
class TaskInfoTable(DefinitionInfoTable): pass

################################################################################
