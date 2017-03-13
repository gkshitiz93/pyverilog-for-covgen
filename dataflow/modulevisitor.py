#-------------------------------------------------------------------------------
# modulevisitor.py
# 
# Module definition visitor
#
# Copyright (C) 2013, Shinya Takamaeda-Yamazaki
# License: Apache 2.0
#-------------------------------------------------------------------------------
from __future__ import absolute_import
from __future__ import print_function
import sys
import os

import pyverilog.vparser.parser
from pyverilog.vparser.ast import *
from pyverilog.dataflow.visit import *
from pyverilog.dataflow.moduleinfo import *
from pyverilog.dataflow.frames import *

class ModuleVisitor(NodeVisitor):
    def __init__(self):
        self.moduleinfotable = ModuleInfoTable()

    def visit_ModuleDef(self, node):
        self.moduleinfotable.addDefinition(node.name, node)
        self.generic_visit(node)

    def visit_Portlist(self, node):
        self.moduleinfotable.addPorts(node.ports)

    def visit_Input(self, node):
        self.moduleinfotable.addSignal(node.name, node)

    def visit_Output(self, node):
        self.moduleinfotable.addSignal(node.name, node)

    def visit_Inout(self, node):
        self.moduleinfotable.addSignal(node.name, node)

    def visit_Parameter(self, node):
        self.moduleinfotable.addConst(node.name, node)
        self.moduleinfotable.addParamName(node.name)

    def visit_Locaparam(self, node):
        self.moduleinfotable.addConst(node.name, node)

    def visit_Function(self, node):
        pass

    def visit_Task(self, node):
        pass
    
    def visit_Assign(self, node):
        pass

    def visit_Always(self, node):
        alwaysdata=AlwaysData(node)
        self.moduleinfotable.addAlways(node=node, alwaysdata=alwaysdata)
        self.generic_visit(node)

    def visit_Block(self, node):
        self.generic_visit(node)
    
    def visit_IfStatement(self, node):
        self.moduleinfotable.addControl(node.cond)
        if node.true_statement is not None: self.visit(node.true_statement)
        if node.false_statement is not None: self.visit(node.false_statement)
    
    def visit_CaseStatement(self, node):
        self.moduleinfotable.addControl(node.comp)
        self._case(node.comp, node.caselist)
    
    def _case(self, comp, caselist):
        if len(caselist) == 0: return
        case = caselist[0]
        if case.statement is not None: self.visit(case.statement)
        if len(caselist) == 1: return
        self._case(comp, caselist[1:])
    
    def visit_CasexStatement(self, node):
        self.visit_CaseStatement(node)
    
    def visit_BlockingSubstitution(self, node):
        self.moduleinfotable.addData(node.right)
        self.moduleinfotable.addState(node.left)

    def visit_NonblockingSubstitution(self, node):
        self.moduleinfotable.addData(node.right)
        self.moduleinfotable.addState(node.left)
    
    def visit_Initial(self, node):
        pass

    def visit_InstanceList(self, node):
        self.moduleinfotable.addInstanceList(node)

    def visit_Instance(self, node):
        self.moduleinfotable.addInstance(node)

    def visit_Pragma(self, node):
        pass

    # get functions
    def get_modulenames(self):
        return self.moduleinfotable.get_names()

    def get_moduleinfotable(self):
        return self.moduleinfotable
