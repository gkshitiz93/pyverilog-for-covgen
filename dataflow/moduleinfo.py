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
from pyverilog.dataflow.visit import *

class ModuleInfo(DefinitionInfo):
    def __init__(self, name, definition):
        DefinitionInfo.__init__(self, name, definition)
        self.always = {}
        self.last = None

    def addAlways(self, node, alwaysdata):
        self.always[node]=alwaysdata
        self.last = node
        return

    def addAlwaysData(self, node, alwaysdata):
        if(node in self.always.keys()):
            self.always[node]=alwaysdata
        else:
            raise verror.DefinitionError('Already defined Always:')
        self.last = node
        return 

    def getAlways(self):
        return self.always

    def getAlwaysData(self, node):
        return self.always[node]

    def getCurrentAlwaysData(self):
        if(self.last is None):
            raise verror.DefinitionError('Already not defined')
        else:
            return self.getAlwaysData(self.last)

class ModuleInfoTable(object):
    def __init__(self):
        self.dict = collections.OrderedDict()
        self.current = None
    def addDefinition(self, name, definition):
        if name in self.dict:
            raise verror.DefinitionError('Already defined: %s' % name)
        self.dict[name] = ModuleInfo(name, definition)
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
    
    def addAlways(self, node, alwaysdata, name=''):
        if(name==''):
            self.dict[self.current].addAlways(node, alwaysdata)
        else:
            self.dict[name].addAlways(node, alwaysdata)
    
    def addAlwaysData(self, node, alwaysdata, name=''):
        if(name==''):
            self.dict[self.current].addAlwaysData(node, alwaysdata)
        else:
            self.dict[name].addAlwaysData(node, alwaysdata)
    
    def getAlways(self, name=''):
        if(name in self.dict.keys()):
            return self.dict[name].getAlways()
        else:
            return None
    
    def getAlwaysData(self, node, name=''):
        if(name==''):
            return self.dict[self.current].getAlwaysData(node)
        else:
            return self.dict[name].getAlwaysData(node)

    def getCurrentAlwaysData(self, name=''):
        if(name==''):
            return self.dict[self.current].getCurrentAlwaysData()
        else:
            return self.dict[name].getCurrentAlwaysData()

