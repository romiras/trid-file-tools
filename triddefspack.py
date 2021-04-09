#!/usr/bin/env python2

#--------------------------------------------------------------------------
# TrIDDefsPack - TrID's definitions packager
# Copyright (C) 2011-2016 Marco Pontello - http://mark0.net
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#--------------------------------------------------------------------------


import os
import sys
import time
import glob
import argparse
import xml.etree.ElementTree as XML
from struct import *
import pickle

PROGRAM_VER = "1.26b"

def header_intro():
    """
    Display the usual presentation, version, (C) notices, etc.
    """
    print
    print "TrIDDefsPack/Py - TrID's defs packager v%s - "\
          "(C) 2011-2016 By M.Pontello" % (PROGRAM_VER)
    print


def errexit(mess, errlev=1):
    """display an error and exit"""
    print "%s: error: %s" % (os.path.split(sys.argv[0])[1], mess)
    sys.exit(errlev)


def get_cmdline():
    """
    Evaluate command line parameters, usage & help.
    """
    parser = argparse.ArgumentParser(
             description="Read a number a TrID's XML definitions \
             and create a new TRD package.",
             formatter_class=argparse.ArgumentDefaultsHelpFormatter,
             prefix_chars='-/+',
             version = "TrIDDefsPack/Python v" + PROGRAM_VER)
    parser.add_argument("filenames", action="store", nargs="*",
                        help = "TrID's definitions (can include path & \
                        wildcards).")
    parser.add_argument("-s", action="store_true", default=False,
                        help = "Strip unneccesary info (remarks, URLs, etc.)")
    parser.add_argument("-u", action="store_true", default=False,
                        help = "update mode (add only defs in the current " +
                        "path to the existing .TRD package)")
    parser.add_argument("-t", action="store", dest="trd",
                        help = "TRD package filename.",
                        default="triddefs.trd")
    res = parser.parse_args()

    CMD = {}
    CMD["files"] = res.filenames
    CMD["strip"] = res.s
    CMD["trd"] = res.trd
    CMD["update"] = res.u
    return CMD


class TridDef(object):
    """
    TrID definition.
    """
    def __init__(self):
        self.reset()
    def __str__(self):
        return "FileType: '%s', Ext: %s, Patterns: %d, Strings: %d" % \
               (self.filetype, "/".join(self.ext),
               len(self.patterns), len(self.strings))

    def reset(self):
        self.name = ""
        self.filetype = ""
        self.ext = []
        self.mime = ""
        self.tag = 0
        self.rem = ""
        self.refurl = ""
        self.user = ""
        self.email = ""
        self.home = ""
        self.filenum = 0
        self.datetime = time.time()
        self.checkstrings = True
        self.refine = ""
        self.patterns = []
        self.strings = []

    def loadXml(self, filename):
        """
        Load data from a TrID's XML definition (*.trid.xml).
        """
        trid = XML.parse(filename).getroot()

        self.reset()
        self.name = os.path.split(filename.encode("ascii", "ignore"))[1]
        self.filetype = trid.findtext("Info/FileType").strip()
        self.ext = trid.findtext("Info/Ext", default="").split("/")
        self.mime = trid.findtext("Info/Mime", default="").strip()
        self.user = trid.findtext("Info/User", default="").strip()
        self.email = trid.findtext("Info/E-Mail", default="").strip()
        self.home = trid.findtext("Info/Home", default="").strip()
        data = trid.findtext("General/FileNum")
        if data.isdigit():
            self.filenum = int(data)
        else:
            self.filenum = 0
        self.checkstrings = trid.findtext("General/CheckStrings",
                               default="False").strip() == "True"

        self.refine = trid.findtext("General/Refine", default="").strip()

        tridx = trid.find("Info/ExtraInfo")
        if tridx is not None:
            self.rem = tridx.findtext("Rem", default="").strip()
            self.refurl = tridx.findtext("RefURL", default="").strip()
            data = tridx.findtext("Tag", default="")
            if data.isdigit():
                self.tag = int(data)
            else:
                self.tag = 0
        tridx = trid.find("General/Date")
        if tridx is not None:
            yy = int(tridx.findtext("Year", default="0").strip())
            mm = int(tridx.findtext("Month", default="0").strip())
            dd = int(tridx.findtext("Day", default="0").strip())
            tridx = trid.find("General/Time")
            hh = int(tridx.findtext("Hour", default="0").strip())
            mn = int(tridx.findtext("Min", default="0").strip())
            ss = int(tridx.findtext("Sec", default="0").strip())
            self.datetime = time.mktime((yy, mm, dd, hh, mn, ss, 0, 0, 0))
            
        elist = trid.findall("FrontBlock/Pattern")
        for pat in elist:
            for patdata in pat.getchildren():
                ppos = 0
                bytes = ""
                if patdata.tag == "Pos":
                    ppos = int(patdata.text)
                elif patdata.tag == "Bytes":
                    pbytes = hex2bytes(patdata.text)
            self.patterns.append( (ppos, pbytes) )

        elist = trid.findall("GlobalStrings/String")
        for ele in elist:
            self.strings.append(ele.text.replace("'", "\x00").upper())

def hex2bytes(string):
    """
    Convert a list of HEX values to a bytes sequence
    """
    bytes = []
    for i in range(0, len(string), 2):
        bytes.append(chr(int(string[i:i+2], 16)))
    return "".join(bytes)


def trdchunk(name, data, opt=False):
    if opt == True:
        if not data:
            return ""
    return name + pack("<H", len(data)) + data


def trddef2bin(triddef, stripinfo):
    DataChunk = ""
    InfoChunk = ""

    InfoChunk += trdchunk("TYPE", triddef.filetype)
    InfoChunk += trdchunk("EXT ", "/".join(triddef.ext))
    InfoChunk += trdchunk("MIME", triddef.mime, opt=True)
    if triddef.tag <> 0:
        InfoChunk += trdchunk("TAG ", pack("<I", triddef.tag))

    if not stripinfo:
        InfoChunk += trdchunk("NAME", triddef.name, opt=True)
        InfoChunk += trdchunk("USER", triddef.user, opt=True)
        InfoChunk += trdchunk("REM ", triddef.rem, opt=True)
        InfoChunk += trdchunk("RURL", triddef.refurl, opt=True)
        InfoChunk += trdchunk("FNUM", pack("<I", triddef.filenum))
        InfoChunk += trdchunk("MAIL", triddef.email, opt=True)
        InfoChunk += trdchunk("HOME", triddef.home, opt=True)

    PatBlock = []
    for pattern in triddef.patterns:
        pos, patbytes = pattern
        PatBlock.append(pack("<HH", pos, len(patbytes)) + patbytes)
    PatBlock = pack("<H", len(triddef.patterns)) + "".join(PatBlock)

    DataChunk += "PATT" + pack("<I", len(PatBlock)) + PatBlock

    if len(triddef.strings):
        StrBlock = []
        for string in triddef.strings:
            StrBlock.append(pack("<I", len(string)) + string)
        StrBlock = pack("<H", len(triddef.strings)) + "".join(StrBlock)
        DataChunk += "STRN" + pack("<I", len(StrBlock)) + StrBlock

    if len(DataChunk) % 2:
        DataChunk += pack("B", 0)
    DataChunk = "DATA" + pack("<I", len(DataChunk)) + DataChunk
    if len(InfoChunk) % 2:
        InfoChunk += pack("B", 0)
    InfoChunk = "INFO" + pack("<I", len(InfoChunk)) + InfoChunk
    DefChunk = DataChunk + InfoChunk
    DefChunk = "DEF " + pack("<I", len(DefChunk)) + DefChunk

    return DefChunk


def trdbuild(deflist, stripflag):
    """create a block of binary defs from a list of TrID definitions"""
    defsdata = []
    for triddef in deflist:
        defsdata.append(trddef2bin(triddef, stripflag))
    defsdata = "".join(defsdata)
    if len(defsdata) % 2:
        defsdata += pack("B", 0)
    return defsdata


def trdpack(defsdata, defsnum):
    """create a TRD container from a block of TrID definitions"""
    defsblock = "DEFS" + pack("<I", len(defsdata)) + defsdata
    defnblock = "DEFN" + pack("<II", 4, defsnum)
    #maybe DEFz with the data part compressed
    tridchunk = "TRID" + defnblock + defsblock
    #maybe TrID with the correct size before data
    container = "RIFF" + pack("<I", len(tridchunk)) + tridchunk
    return container


def buildDefList(path):
    """build a list of defs from a path, with the new dir structure"""
    #defs at the specified path
    deflist = glob.glob(os.path.join(path, "*.trid.xml"))
    #then all the 1st level subs 0, a, ..., z
    deflist = deflist + glob.glob(os.path.join(path, "[0a-z]\\*.trid.xml"))
    return deflist


def getDefsBlockFromTrd(filename):
    """
    Get the block of TrID definition from a TRD package file
    """
    triddefs = []
    package = ""
    defsnum = 0
    if os.path.exists(filename):
        with open(filename, "rb") as ftrd:
            package = ftrd.read()
        # some sanity checks needed
        infoBlock = package[12:12+12]
        defsnum = unpack("<i", infoBlock[-4:])[0]
        blen= unpack("<i", package[28:28+4])[0]
        package = package[32:32+blen]
    return package, defsnum


def main():
    header_intro()
    CMD = get_cmdline()

    print "Building files list..."
    filenames = []
    updatetempname = "triddefspack.tmp"

    
    if not CMD["files"]:
        filenames += glob.glob("*.trid.xml")
        if len(filenames) == 0 or CMD["update"] == False:
            filenames += buildDefList("defs")
            CMD["update"] = False
            print "No update!"
    else:
        for filename in CMD["files"]:
            if os.path.isdir(filename):
                filenames += buildDefList(filename)
            else:
                if os.path.exists(filename):
                    filenames.append(filename)
    filenames = sorted(set(filenames))

    deflist = []
    print "Found %d definitions." % len(filenames)
    print "Reading..."

    c = 0
    for filename in filenames:
        triddef = TridDef()
        try:
            triddef.loadXml(filename)
        except XML.ParseError as e:
            print "\n\nError parsing def %s: %s" % (filename, e)
            time.sleep(20)
            sys.exit(1)
        except:
            raise
        deflist.append(triddef)
        c +=1
        if c == 17:
            print "\r%5d %s" % (len(deflist), (triddef.filetype+" "*70)[:70]),
            c = 0

    print "\r%s\r" % (" " * 76),

    print "Packing..."
    defnumnew = len(deflist)
    defdatanew = trdbuild(deflist, CMD["strip"])
    if CMD["update"]:
        defdataold, defnumold = getDefsBlockFromTrd("triddefs.trd")
        if os.path.exists(updatetempname):
            #read last update data and remove them from the old package
            with open(updatetempname, "r") as tf:
                lastupdatedata = pickle.load(tf)
            defdataold = defdataold[lastupdatedata["deflen"]:]
            defnumold -= lastupdatedata["defnum"]
        defdata = defdatanew + defdataold
        defnum = defnumnew + defnumold
        print "Adding existing %i definitions..." % (defnumold)
        #write the data necessary to id the new section, to be
        #removed next time
        with open(updatetempname, "w") as tf:
            lastupdatedata = {"defnum": defnumnew,
                              "deflen": len(defdatanew)}
            pickle.dump(lastupdatedata, tf)
    else:
        defdata = defdatanew
        defnum = defnumnew
        #delete the temporary update file
        if os.path.exists(updatetempname):
            os.remove(updatetempname)
    trddata = trdpack(defdata, defnum)
    print "Package size: %d bytes. Definitions: %d" % (len(trddata), defnum)

    with open(CMD["trd"], "wb") as ftrd:
        ftrd.write(trddata)
    print "File %s written." % (CMD["trd"])


if __name__ == '__main__':
    main()
