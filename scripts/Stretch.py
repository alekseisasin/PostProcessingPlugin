# Copyright (c) 2017 Christophe Baribaud 2017
# This PostProcessingPlugin script is released under the terms of the AGPLv3 or higher.
# Python implementation of https://github.com/electrocbd/post_stretch
# Correction of hole sizes, cylinder diameters and curves
#
# WARNING This script has never been tested with several extruders
#
from ..Script import Script
import math
import numpy as np
from UM.Logger import Logger

class GCodeStep():
    def __init__(self,step,x,y,z,e,f,comment):
        self.step = step
        self.x = x
        self.y = y
        self.z = z
        self.e = e
        self.f = f
        self.comment = comment

class Stretch(Script):
    def __init__(self):
        super().__init__()

    def getSettingDataString(self):
        return """{
            "name":"Post stretch script",
            "key": "Stretch",
            "metadata": {},
            "version": 2,
            "settings":
            {
                "stretch":
                {
                    "label": "Stretch distance",
                    "description": "Distance by which the points are moved by the correction effect. The higher this value, the higher the effect",
                    "unit": "mm",
                    "type": "float",
                    "default_value": 0.08,
                    "minimum_value": 0,
                    "minimum_value_warning": 0,
                    "maximum_value_warning": 0.2
                },
                "line_width":
                {
                    "label": "Wall size",
                    "description": "Average value of line width, should match roughly the corresponding parameter of Cura/CuraEngine",
                    "unit": "mm",
                    "type": "float",
                    "default_value": 0.7,
                    "minimum_value": 0.1,
                    "maximum_value_warning": 1
                }
            }
        }"""

    def execute(self, data):
        self.line_width = self.getSettingValueByKey("line_width")
        self.stretch = self.getSettingValueByKey("stretch")
        retdata = []
        layerSteps = []
        current_x = 0.
        current_y = 0.
        current_z = 0.
        current_e = 0.
        current_f = 0.

        self.output_x = 0.
        self.output_y = 0.
        self.output_z = 0.
        self.output_e = 0.
        self.output_f = 0.

        layer_z = 0.
        for layer in data:
            lines = layer.rstrip("\n").split("\n")
            for line in lines:
                comment = ""
                if line.find(';') >= 0:
                    comment = line[line.find(';'):]
                if self.getValue(line,'G') == 0:
                    current_x = self.getValue(line,'X',current_x)
                    current_y = self.getValue(line,'Y',current_y)
                    current_z = self.getValue(line,'Z',current_z)
                    current_e = self.getValue(line,'E',current_e)
                    current_f = self.getValue(line,'F',current_f)
                    onestep = GCodeStep(0,current_x,current_y,current_z,current_e,current_f,comment)
                elif self.getValue(line,'G') == 1:
                    current_x = self.getValue(line,'X',current_x)
                    current_y = self.getValue(line,'Y',current_y)
                    current_z = self.getValue(line,'Z',current_z)
                    current_e = self.getValue(line,'E',current_e)
                    current_f = self.getValue(line,'F',current_f)
                    onestep = GCodeStep(1,current_x,current_y,current_z,current_e,current_f,comment)
                elif self.getValue(line,'G') == 92:
                    current_x = self.getValue(line,'X',current_x)
                    current_y = self.getValue(line,'Y',current_y)
                    current_z = self.getValue(line,'Z',current_z)
                    current_e = self.getValue(line,'E',current_e)
                    current_f = self.getValue(line,'F',current_f)
                    onestep = GCodeStep(-1,current_x,current_y,current_z,current_e,current_f,comment)
                else:
                    onestep = GCodeStep(-1,current_x,current_y,current_z,current_e,current_f,line);
                if current_z != layer_z:
                    Logger.log("d","Layer Z " + "{:.3f}".format(layer_z) + " " + str(len(layerSteps)) + " steps")
                    if len(layerSteps):
                        retdata.append(self.processLayer(layerSteps))
                    layerSteps = []
                    layer_z = current_z
                layerSteps.append(onestep)
        if len(layerSteps):
            retdata.append(self.processLayer(layerSteps))
        return retdata

    def processLayer(self,layerSteps):
        layergcode = ""
        self.vd1 = np.empty((0,2)) #Start points of segments of already deposited material for this layer
        self.vd2 = np.empty((0,2)) #End points of segments of already deposited material for this layer
        current_e = layerSteps[0].e
        vPos = np.empty((0,2))
        iflush = 0
        for i in range(len(layerSteps)):
            if i==0:
                current_e = layerSteps[i].e
            if current_e == layerSteps[i].e:
                vTrans = np.copy(vPos)
                if len(vPos) >= 2:
                    self.workOnSequence(vPos,vTrans)
                layergcode = self.generate(layerSteps,iflush,i,vTrans,layergcode)
                iflush = i
                vPos = np.empty((0,2))
            if layerSteps[i].step == 0 or layerSteps[i].step == 1:
                vPos = np.concatenate([vPos,np.array([[layerSteps[i].x,layerSteps[i].y]])])
            current_e = layerSteps[i].e
        if len(vPos):
            vTrans = np.copy(vPos)
        if len(vPos)>=2:
            self.workOnSequence(vPos,vTrans)
        layergcode = self.generate(layerSteps,iflush,len(layerSteps),vTrans,layergcode)
        return layergcode

    def dumpPos(self,onestep):
        sout = ""
        if onestep.f != self.output_f:
            self.output_f = onestep.f
            sout += " F"
            sout += "{:.0f}".format(self.output_f).rstrip('.')
        if onestep.x != self.output_x or onestep.y != self.output_y or onestep.z != self.output_z:
            self.output_x = onestep.x
            sout += " X"
            sout += "{:.3f}".format(self.output_x).rstrip('0').rstrip('.')
            self.output_y = onestep.y
            sout += " Y"
            sout += "{:.3f}".format(self.output_y).rstrip('0').rstrip('.')
        if onestep.z != self.output_z:
            self.output_z = onestep.z
            sout += " Z"
            sout += "{:.3f}".format(self.output_z).rstrip('0').rstrip('.')
        if onestep.e != self.output_e:
            self.output_e = onestep.e
            sout += " E"
            sout += "{:.5f}".format(self.output_e).rstrip('0').rstrip('.')
        return sout

    def generate(self,layerSteps,i,iend,vPos,layergcode):
        ipos = 0
        while i < iend:
            if layerSteps[i].step == 0:
                sout = "G0" + self.dumpPos(layerSteps[i])
                layergcode = layergcode + sout + "\n"
                ipos = ipos + 1
            elif layerSteps[i].step == 1:
                layerSteps[i].x = vPos[ipos][0]
                layerSteps[i].y = vPos[ipos][1]
                sout = "G1" + self.dumpPos(layerSteps[i])
                layergcode = layergcode + sout + "\n"
                ipos = ipos + 1
            else:
                layergcode = layergcode + layerSteps[i].comment + "\n"
            i = i + 1
        return layergcode


    def workOnSequence(self,vPos,vTrans):
        if len(vPos)>2 and ((vPos[len(vPos)-1]-vPos[0])**2).sum(0) < 0.3*0.3:
            self.wideCircle(vPos,vTrans)
        else:
            self.wideTurn(vPos,vTrans)
        self.pushWall(vPos,vTrans)
        if (len(vPos)):
            self.vd1 = np.concatenate([self.vd1,np.array(vPos[:-1])])
            self.vd2 = np.concatenate([self.vd2,np.array(vPos[1:])])

    def wideCircle(self,vPos,vTrans):
        '''
        Similar to wideTurn
        The first and last point of the sequence are the same,
        so it is possible to extend the end of the sequence with its beginning when seeking for triangles
        '''
        d1 = self.line_width / 2.0
        d4 = self.stretch
        iextra = np.floor_divide(len(vPos),3) # Nb of extra points
        i1 = 0
        i = 0
        i3 = 0
        while i<len(vPos):
            vPosAfter = np.resize(np.roll(vPos,-i-1,0),(iextra,2))
            good_triangle = True
            dp = ((vPos[i]-vPosAfter)**2).sum(1)
            if np.amax(dp) < d1*d1:
                good_triangle = False
            else:
                i3 = np.argmax(dp>=d1*d1)
            if good_triangle:
                vPosBefore = np.resize(np.roll(vPos,-i,0)[::-1],(iextra,2))
                dp = ((vPos[i]-vPosBefore)**2).sum(1)
                if np.amax(dp) < d1*d1:
                    good_triangle = False
                else:
                    i1 = np.argmax(dp>=d1*d1)
            if good_triangle:
                rd=((vPosAfter[i3]-vPosBefore[i1])**2).sum(0)
                r=((vPos[i]-vPosBefore[i1])*(vPosAfter[i3]-vPosBefore[i1])).sum(0)
                if np.fabs(r) < 1000.0*np.fabs(rd):
                    r /= rd
                else:
                    r = 0.5
                pp=vPosBefore[i1] + r*(vPosAfter[i3]-vPosBefore[i1])
                dpp=np.sqrt(((pp-vPos[i])**2).sum(0))
                if dpp > 0.001:
                    vTrans[i] = vPos[i] - (d4/dpp)*(pp-vPos[i])

            i = i + 1
        return

    def wideTurn(self,vPos,vTrans):
        '''
        We have to select three points in order to form a triangle
        These three points should be far enough from each other to have
        a reliable estimation of the orientation of the current turn
        '''
        d1 = self.line_width / 2.0
        d4 = self.stretch
        i1 = 0
        i = 1
        i3 = 2
        while i+1<len(vPos):
            good_triangle = True
            dp = ((vPos[i]-vPos[i+1:])**2).sum(1)
            if np.amax(dp) < d1*d1:
                good_triangle = False
            else:
                i3 = i+1 + np.argmax(dp>=d1*d1)
            if good_triangle:
                dp = ((vPos[i]-vPos[i-1::-1])**2).sum(1)
                if np.amax(dp) < d1*d1:
                    good_triangle = False
                else:
                    i1 = i-1 - np.argmax(dp>=d1*d1)
            if good_triangle:
                rd=((vPos[i3]-vPos[i1])**2).sum(0)
                r=((vPos[i]-vPos[i1])*(vPos[i3]-vPos[i1])).sum(0)
                if np.fabs(r) < 1000.0*np.fabs(rd):
                    r /= rd
                else:
                    r = 0.5
                pp=vPos[i1] + r*(vPos[i3]-vPos[i1])
                dpp=np.sqrt(((pp-vPos[i])**2).sum(0))
                if dpp > 0.001:
                    vTrans[i] = vPos[i] - (d4/dpp)*(pp-vPos[i])
            i = i + 1
        return

    def pushWall(self,vPos,vTrans):
        d2 = self.line_width / 2.0
        d4 = self.stretch
        mrot = np.array([[0,-1],[1,0]]) # Quarter turn
        for i in range(len(vPos)):
            i1 = i
            i2 = i+1
            if i2 == len(vPos):
                i2 = i-1
            xm = vPos[i1]
            xperp = np.dot(mrot,vPos[i2]-vPos[i1])
            xperp = xperp / np.sqrt((xperp**2).sum(-1))
            xp1 = xm + xperp * d2
            toucheplus = False
            xp2 = xm - xperp * d2
            touchemoins = False
            if (self.vd1.shape[0]):
                # python is abysmally slow
                # It is necessary to dive into numpy as fast as possible
                p = xp1
                r = np.clip(((p-self.vd1)*(self.vd2-self.vd1)).sum(1) / ((self.vd2-self.vd1)*(self.vd2-self.vd1)).sum(1),0.,1.)
                '''
                Already deposited material is stored as segments.
                vd1 is the array of the starting points of the segments
                vd2 is the array of the ending points of the segments
                For example, segment nr 8 starts at position self.vd1[8] and ends at position self.vd2[8]
                For each segment of already deposited material, r is the index of the nearest point of this segment
                from the point p
                r=0 means the start of the segment, r=1 means the end of the segment,
                r=0.5 means the middle between the start and the end of the segment, etc.
                '''
                pp = self.vd1 + r[:,np.newaxis]*(self.vd2-self.vd1)
                '''
                pp is the array of the nearest points of each segment from the point p
                '''
                dist = ((p-pp)*(p-pp)).sum(1)
                '''
                dist is the array of the squares of the distances between p and each segment
                '''
                if np.amin(dist) <= d2*d2:
                    toucheplus = True
                '''
                Now the same computation with the point xp2 at the other side of the
                current segment
                '''
                p = xp2
                r = np.clip(((p-self.vd1)*(self.vd2-self.vd1)).sum(1) / ((self.vd2-self.vd1)*(self.vd2-self.vd1)).sum(1),0.,1.)
                pp = self.vd1 + r[:,np.newaxis]*(self.vd2-self.vd1)
                dist = ((p-pp)*(p-pp)).sum(1)
                if np.amin(dist) <= d2*d2:
                    touchemoins = True
            if toucheplus and not touchemoins:
                xp = vTrans[i1] + xperp * d4
                assert xp[0] >= 0 and xp[0] < 200
                assert xp[1] >= 0 and xp[1] < 200
                vTrans[i1] = xp
            elif not toucheplus and touchemoins:
                xp = vTrans[i1] - xperp * d4;
                assert xp[0] >= 0 and xp[0] < 200
                assert xp[1] >= 0 and xp[1] < 200
                vTrans[i1] = xp
            if toucheplus and touchemoins:
                vTrans[i1] = vPos[i1]

