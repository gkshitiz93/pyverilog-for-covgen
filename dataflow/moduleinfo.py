from __future__ import absolute_import
from __future__ import print_function
import sys
import os
import re
import copy
import collections

import pyverilog
import pyverilog.utils.signaltype as signaltype
import pyverilog.utils.util as util
import pyverilog.utils.verror as verror
from pyverilog.utils.scope import ScopeLabel, ScopeChain
from pyverilog.vparser.ast import *
from pyverilog.dataflow.visit import *


def unique(a):
    return list(set(a))

def intersect(a, b):
    return list(set(a) & set(b))

def union(a, b):
    return list(set(a) | set(b))

class AlwaysData(object):
    def __init__(self, node):
        self.node = node
        self.data = {}
        self.control = {}
        self.state = {}
        self.comb = None
        self._getComb()
    def addData(self, name):
        if name in self.data.keys():
            self.data[name]+=1
        else:
            self.data[name]=1
    
    def getData(self):
        return self.data
    
    def addState(self, name):
        if name in self.state.keys():
            self.state[name]+=1
        else:
            self.state[name]=1

    def getState(self):
        return self.state
    def addControl(self, name):
        if name in self.control.keys():
            self.control[name]+=1
        else:
            self.control[name]=1
    
    def getControl(self):
        return self.control

    def printInfo(self, buf=sys.stdout):
        buf.write('AlwaysData:\n')
        if(self.data):
            buf.write('Data:\n')
            string=''
            for var in self.data.keys():
                string+=var + '[' + str(self.data[var]) + '] '
            buf.write(string + '\n')
        if(self.control):
            buf.write('Control:\n')
            string=''
            for var in self.control.keys():
                string+=var + '[' + str(self.control[var]) + '] '
            buf.write(string + '\n')
        if(self.state):
            buf.write('State:\n')
            string=''
            for var in self.state.keys():
                string+=var + '[' + str(self.state[var]) + '] '
            buf.write(string + '\n')
    
    def getinfo(self):
        sens = None
        senslist = []
        clock_edge = None
        clock_name = None
        clock_bit = None
        reset_edge = None
        reset_name = None
        reset_bit = None

        for l in self.node.sens_list.list:
            if l.sig is None:
                continue
            if isinstance(l.sig, pyverilog.vparser.ast.Pointer):
                signame = self._get_signal_name(l.sig.var)
                bit = int(l.sig.ptr.value)
            else:
                signame = self._get_signal_name(l.sig)
                bit = 0
            if signaltype.isClock(signame):
                clock_name = signame
                clock_edge = l.type
                clock_bit = bit
            elif signaltype.isReset(signame):
                reset_name = signame
                reset_edge = l.type
                reset_bit = bit
            else:
                senslist.append(l)

        if clock_edge is not None and len(senslist) > 0:
            raise verror.FormatError('Illegal sensitivity list')
        if reset_edge is not None and len(senslist) > 0:
            raise verror.FormatError('Illegal sensitivity list')

        return (clock_name, clock_edge, clock_bit, reset_name, reset_edge, reset_bit, senslist)
    
    def _getComb(self):
        clock_name = None
        for l in self.node.sens_list.list:
            if l.sig is None:
                continue
            if isinstance(l.sig, pyverilog.vparser.ast.Pointer):
                signame = self._get_signal_name(l.sig.var)
                bit = int(l.sig.ptr.value)
            else:
                signame = self._get_signal_name(l.sig)
                bit = 0
            if signaltype.isClock(signame):
                clock_name = signame
                break

        if clock_name is None:
            self.comb=True
        else:
            self.comb=False
    
    def isComb(self):
        return self.comb
    
    def _get_signal_name(self, n):
        if isinstance(n, Identifier):
            return n.name
        if isinstance(n, Pointer):
            return self._get_signal_name(n.var)
        if isinstance(n, Partselect):
            return self._get_signal_name(n.var)
        return None

class ModuleInfo(DefinitionInfo):
    def __init__(self, name, definition):
        DefinitionInfo.__init__(self, name, definition)
        self.always = {}
        self.statelist = {}
        self.interesting = []
        self.last = None
        self.instances = []
        self.instancelists = []
        self.arraylimiters = {}

    def addlimiters(self, node, lsb, msb):
        self.arraylimiters[node]=tuple(lsb, msb)
    
    def getlimiters(self, node):
        return self.arraylimiters[node]

    def addInstance(self, node):
        self.instances.append(node)
    
    def addInstanceList(self, node):
        self.instancelists.append(node)
    
    def getInstance(self):
        return self.instances
    
    def getInstanceList(self):
        return self.instancelists

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
    
    def addData(self, var):
        alwaysdata=self.getCurrentAlwaysData()
        for name in map(str,var.getIdentifiers([])):
            alwaysdata.addData(name)

    def getData(self):
        return self.getCurrentAlwaysData().getData()
    
    def addState(self, var):
        alwaysdata=self.getCurrentAlwaysData()
        for node in var.getIdentifiers([]):
            self.statelist[str(node)]=alwaysdata
            alwaysdata.addState(str(node))

    def getState(self):
        return self.getCurrentAlwaysData().getState()

    def getAlwaysfromState(self, name):
        if name in self.statelist.keys():
            return self.statelist[name]
        else:
            return None

    def addControl(self, var):
        alwaysdata=self.getCurrentAlwaysData()
        for name in map(str,var.getIdentifiers([])):
            alwaysdata.addControl(name)

    def getControl(self):
        return self.getCurrentAlwaysData().getControl()

    def findInteresting(self):
        for al in self.always.values():
            if al.isComb():
                #Combinational block
                self.interesting.extend(filter(lambda x: x in self.getstatelist(al),al.getControl().keys()))
            else:
                self.interesting.extend(filter(lambda x: x in al.getState().keys(),al.getControl().keys()))
        
        self.interesting=unique(self.interesting)

    def getstatelist(self, always):
        ret = []
        for al in self.always.values():
            if al.isComb():
                common = list(filter(lambda x: x in always.getState().keys(), union(al.getControl().keys(), al.getData().keys())))
                if common:
                    ret.extend(self.getstatelist(al))
            else:
                common = list(filter(lambda x: x in always.getState().keys(), union(al.getControl().keys(), al.getData().keys())))
                if common:
                    ret.extend(al.getState().keys())
        return ret
    
    def getInteresting(self):
        return self.interesting
    
    def printInfo(self, buf=sys.stdout):
        for data in self.always.values():
            data.printInfo(buf)

        if self.interesting:
            buf.write('\nInteresting:\n')
            for name in self.interesting:
                buf.write(name + ' ')
            buf.write('\n')

        if self.instances:
            for node in self.instances:
                self.printInstance(node, buf)

        if self.instancelists:
            for ilist in self.instancelists:
                for node in ilist.instances:
                    self.printInstance(node, buf)

    def printInstance(self, node, buf=sys.stdout):
        buf.write('Instance: ' + node.module + ' - ' + node.name)
        if node.array:
            buf.write('[' + str(node.msb) + ':' + str(node.lsb) + ']')
        buf.write('\n')

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
    def getCurrent(self):
        return self.current
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
    
    def addlimiters(self, node, lsb, msb):
        if(name==''):
            self.dict[self.current].addlimiters(node, lsb, msb)
        else:
            self.dict[name].addlimiters(node, lsb, msb)

    def addlimiters(self, node):
        if(name==''):
            return self.dict[self.current].getlimiters(node)
        else:
            return self.dict[name].getlimiters(node)
    
    def addInstance(self, node, name=''):
        if(name==''):
            self.dict[self.current].addInstance(node)
        else:
            self.dict[name].addInstance(node)
    
    def addInstanceList(self, node, name=''):
        if(name==''):
            self.dict[self.current].addInstanceList(node)
        else:
            self.dict[name].addInstanceList(node)
    
    def getInstance(self, name=''):
        if(name==''):
            return self.dict[self.current].getInstance()
        else:
            return self.dict[name].getInstance()
    
    def getInstanceList(self, name=''):
        if(name==''):
            return self.dict[self.current].getInstanceList()
        else:
            return self.dict[name].getInstanceList()
    
    def getInteresting(self, name=''):
        if(name==''):
            return self.dict[self.current].getInteresting()
        else:
            return self.dict[name].getInteresting()
    
    def findInteresting(self):
        for name in self.dict.keys():
            self.dict[name].findInteresting()
    
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
            return self.dict[self.current].getAlways()
    
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

    def addData(self, var, name=''):
        if(name==''):
            self.dict[self.current].addData(var)
        else:
            self.dict[name].addData(var)

    def getData(self, name=''):
        if(name==''):
            return self.dict[self.current].getData()
        else:
            return self.dict[name].getData()
    
    def addControl(self, var, name=''):
        if(name==''):
            self.dict[self.current].addControl(var)
        else:
            self.dict[name].addControl(var)

    def getControl(self, name=''):
        if(name==''):
            return self.dict[self.current].getControl()
        else:
            return self.dict[name].getControl()
    
    def getAlwaysfromState(self, varname, name=''):
        if(name==''):
            return self.dict[self.current].getAlwaysfromState(varname)
        else:
            return self.dict[name].getAlwaysfromState(varname)
    
    def addState(self, var, name=''):
        if(name==''):
            self.dict[self.current].addState(var)
        else:
            self.dict[name].addState(var)

    def getState(self, name=''):
        if(name==''):
            return self.dict[self.current].getState()
        else:
            return self.dict[name].getState()

    def getModule(self, name=''):
        if(name==''):
            return self.dict[self.current]
        else:
            return self.dict[name]

    def isModule(self, name):
        return(name in self.dict.keys())
            
