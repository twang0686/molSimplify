import pytest
import argparse
import os
import openbabel as ob
import numpy as np
from molSimplify.Scripts.inparse import *
from molSimplify.Scripts.geometry import *
from molSimplify.Scripts.generator import *
from molSimplify.Classes.globalvars import *
from molSimplify.Classes.mol3D import mol3D
from molSimplify.Classes.mol3D import distance
from molSimplify.Classes.atom3D import atom3D
from pkg_resources import resource_filename, Requirement

def fuzzy_equal(x1,x2,thresh):
    return np.fabs(float(x1)-float(x2)) < thresh

#check whether the string is a integral/float/scientific 
def is_number(s):
        try:
          float(s)
          return True
        except ValueError:
          return False

def fuzzy_compare_xyz(xyz1,xyz2,thresh):
    fuzzyEqual=False
    mol1 = mol3D()
    mol1.readfromxyz(xyz1)
    mol2 = mol3D()
    mol2.readfromxyz(xyz2)
    mol1,U,d0,d1 = kabsch(mol1,mol2)
    rmsd12 = mol1.rmsd(mol2)
    print('rmsd is ' +'{0:.2f}'.format(rmsd12))
    if rmsd12 < thresh:
        fuzzyEqual=True
    return fuzzyEqual

def getAllLigands(xyz):
    mymol3d = mol3D()
    mymol3d.readfromxyz(xyz)
    # OUTPUT
    #   -mol3D: mol3D of all ligands
    mm = mymol3d.findMetal()[0]
    mbonded = mymol3d.getBondedAtoms(mm)
    ligands=[]
    ligAtoms=[]
    #Get the 1st atom of one ligand
    for iatom in mbonded:
        if iatom not in ligAtoms:
           lig = [iatom]
           oldlig = []
           while len(lig) > len(oldlig):
               #make a copy of lig
               oldlig = lig[:]
               for i in oldlig:
                   lbonded = mymol3d.getBondedAtoms(i)
                   for j in lbonded:
                       if (j != mm) and (j not in lig):
                           lig.append(j)
           newlig = mol3D()
           for i in lig:
               newlig.addAtom(mymol3d.atoms[i])
               ligAtoms.append(i)
           ligands.append(newlig)
    print "Ligand analysis of xyz file: ",xyz
    print "There are ",len(ligands)," ligand(s) bonded with metal center\
            ",mm," in the complex"
    for i in range(0,len(ligands)):
        print "Number of atoms in ligand # ",i," : ",ligands[i].natoms
    return ligands


def getMetalLigBondLength(mymol3d):
    # findMetal only returns 1 metal atom?
    # TG: fixed findmetal to return a list
    mm = mymol3d.findMetal()[0]
    bonded = mymol3d.getBondedAtoms(mm)
    blength = []
    for i in bonded:
        blength.append(distance(mymol3d.atoms[mm].coords(),mymol3d.atoms[i].coords()))
    return blength

# Compare number of atoms
def compareNumAtoms(xyz1,xyz2):
    print "Checking total number of atoms"
    mol1 = mol3D()
    mol1.readfromxyz(xyz1)
    mol2 = mol3D()
    mol2.readfromxyz(xyz1)
   # Compare number of atoms
    passNumAtoms = (mol1.natoms == mol2.natoms)
    print "Pass total number of atoms check: ",passNumAtoms
    return passNumAtoms

# Compare Metal Ligand Bond Length
def compareMLBL(xyz1,xyz2,thresh):
    print "Checking metal-ligand bond length"
    mol1 = mol3D()
    mol1.readfromxyz(xyz1)
    mol2 = mol3D()
    mol2.readfromxyz(xyz1)
    bl1 = getMetalLigBondLength(mol1)
    bl2 = getMetalLigBondLength(mol2)
    passMLBL =True
    for i in range(0,len(bl1)):
        if not fuzzy_equal(bl1[i],bl2[i],thresh):
            print "Error! Metal-Ligand bondlength mismatch for bond # ",i
            passMLBL = False
    print "Pass metal-ligand bond length check: ",passMLBL
    print "Threshold for bondlength difference: ",thresh
    return passMLBL

# Compare Ligand Geometry
def compareLG(xyz1,xyz2,thresh):
    print "Checking the Ligand Geometries"
    passLG = True
    ligs1 = getAllLigands(xyz1)
    ligs2 = getAllLigands(xyz2)
    if len(ligs1) != len(ligs2):
        pssLG = False
        return passLG
    for i in range(0,len(ligs1)):
        print "Checking geometry for ligand # ",i
        ligs1[i],U,d0,d1 = kabsch(ligs1[i],ligs2[i])
        rmsd12 = ligs1[i].rmsd(ligs2[i])
        print('rmsd is ' +'{0:.2f}'.format(rmsd12))
        if rmsd12 > thresh:
            passLG=False
            return passLG
    print "Pass ligand geometry check: ",passLG
    print "Threshold for ligand geometry RMSD difference: ",thresh
    return passLG

def compareOG(xyz1,xyz2,thresh):
    print "Checking the overall geometry"
    passOG = fuzzy_compare_xyz(xyz1,xyz2,thresh)
    print "Pass overall geometry check: ",passOG
    print "Threshold for overall geometry check: ",thresh
    return passOG


def compareGeo(xyz1,xyz2,threshMLBL,threshLG,threshOG):
    # Compare number of atoms
    passNumAtoms = compareNumAtoms(xyz1,xyz2)
    # Compare Metal ligand bond length 
    passMLBL = compareMLBL(xyz1,xyz2,threshMLBL)
    # Compare Single ligand geometry
    passLG = compareLG(xyz1,xyz2,threshLG)
    # Compare gross match of overall complex
    passOG = compareOG(xyz1,xyz2,threshOG)
    # FF free test
    # ANN set bond length test
    # covalent radii test
    return [passNumAtoms,passMLBL,passLG,passOG]

def jobname(infile):
    name=os.path.basename(infile)
    name=name.replace(".in","")
    return name

def jobdir(infile):
    name = jobname(infile)
    homedir = os.path.expanduser("~")
    mydir=homedir+'/Runs/'+name
    return mydir

def parse4test(infile,tmpdir,isMulti=False):
    name = jobname(infile)
    f=tmpdir.join(os.path.basename(infile))
    newname = f.dirname+"/"+os.path.basename(infile)
    data=open(infile).readlines()
    newdata=""
    hasJobdir = False
    hasName = False
    for line in data:
        if not (("-jobdir" in line) or ("-name" in line)):
            newdata+=line
        if ("-lig " in line) and (".smi" in line):#Need to parse the dir of smi file
            smi = line.strip('\n').split()[1]
            abs_smi = os.path.dirname(infile)+'/'+smi
            newdata+="-lig "+abs_smi+"\n"
            #fsmi = tmpdir.join(smi)
            #oldsmi=os.path.dirname(infile)+"/"+smi
            #smidata=open(oldsmi).read()
            #fsmi.write(smidata)
            #print "smi file is copied to the temporary running folder!"
    newdata+="-jobdir "+name+"\n"
    if isMulti == False:
      newdata+="-name "+name+"\n"
    print newdata
    f.write(newdata)
    print "Input file parsed for test is located: ",newname
    return newname

def parse4testNoFF(infile,tmpdir):
    name = jobname(infile)
    newname = name+"_noff" 
    newinfile = name+"_noff.in"
    f=tmpdir.join(newinfile)
    fullnewname = f.dirname+"/"+newinfile
    data=open(infile).readlines()
    newdata=""
    hasJobdir = False
    hasName = False
    hasFF = False
    for line in data:
        if ("-ff " in line):
            hasFF=True
            break
    if not hasFF:
        print "No FF optimization used in original input file. No need to do further test."
        fullnewname = ""
    else:
        print "FF optimization used in original input file. Now test for no FF result."
        for line in data:
            if not (("-jobdir" in line) or ("-name" in line) or ("-ff " in line) ):
                newdata+=line
        newdata+="-jobdir "+newname+"\n"
        newdata+="-name "+newname+"\n"
        print newdata
        f.write(newdata)
        print "Input file parsed for no FF test is located: ",fullnewname
    return fullnewname

#compare the report, split key and values, do 
# fuzzy comparison on the values
def compare_report_new(report1,report2):
    data1=open(report1,'r').readlines()
    data2=open(report2,'r').readlines()
    if data1 and data2:
        Equal = True
    else:
        Equal = False
        print('File not found:') 
        if not data1:
            print('missing: ' + str(report1))
        if not data2:
            print('missing: ' + str(report2))
    if Equal:
       for i in range(0,len(data1)):
           if Equal:
               e1=data1[i].split(',')
               [key1,val1]=e1[0:2]
               e2=data2[i].split(',')
               [key2,val2]=e2[0:2]
               val1=val1.strip('[]')
               val2=val1.strip('[]')
               if key1 != key2:
                   Equal=False
                   print "Report compare failed for ",report1,report2
                   print "keys don't match on line ",i
               else:
                   #see whether the values are numbers or text
                   if is_number(val1) and is_number(val2):
                       Equal = fuzzy_equal(val1,val2,1e-4)
                   else:
                       Equal = (val1 ==val2)
                   if not Equal:
                      print "Report compare failed for ",report1,report2
                      print "Values don't match on line ",i+1
           else:
               break
    return Equal

#When generating multiple files from the 1 input file
#Compare the test directory and reference directory for
#Number of xyz file, xyz file names
def checkMultiFileGen(myjobdir,refdir):
    passMultiFileCheck=True
    myfiles=[ i for i in os.listdir(myjobdir) if ".xyz" in i ]
    reffiles=[ i for i in os.listdir(refdir) if ".xyz" in i ]
    print "Run directory:", myjobdir
    print "Generated xyz:", myfiles
    print "Reference directory:", refdir
    print "Ref xyz:", reffiles
    print "Generated ",len(myfiles)," files, expecting ",len(reffiles)
    if len(myfiles) != len(reffiles):
        passMultiFileCheck=False
        print "Error! Numbers don't match!"
    else:
        for ref in reffiles:
            if ref not in myfiles:
              print "xyz file ",ref, " is missing in generated file folder"
              passMultiFileCheck=False
    return [passMultiFileCheck,myfiles]




def runtest(tmpdir,name,threshMLBL,threshLG,threshOG):
    infile = resource_filename(Requirement.parse("molSimplify"),"tests/inputs/"+name+".in")
    newinfile = parse4test(infile,tmpdir)
    args =['main.py','-i', newinfile]
    startgen(args,False,False)
    myjobdir=jobdir(infile)
    output_xyz = myjobdir + '/'+ name + '.xyz'
    output_report = myjobdir + '/'+ name + '.report'
    ref_xyz = resource_filename(Requirement.parse("molSimplify"),"tests/refs/"+name+".xyz")
    ref_report = resource_filename(Requirement.parse("molSimplify"),"tests/refs/"+name+".report")
    print "Test input file: ", newinfile
    print "Test output files are generated in ",myjobdir
    print "Output xyz file: ", output_xyz
    pass_xyz=compareGeo(output_xyz,ref_xyz,threshMLBL,threshLG,threshOG)
    [passNumAtoms,passMLBL,passLG,passOG] = pass_xyz
    pass_report = compare_report_new(output_report,ref_report)
    print "Reference xyz file: ", ref_xyz
    print "Test report file: ", output_report
    print "Reference report file: ", ref_report
    print "Reference xyz status: ", pass_xyz
    print "Reference report status: ", pass_report
    return [passNumAtoms, passMLBL, passLG, passOG, pass_report]

def runtestNoFF(tmpdir,name,threshMLBL,threshLG,threshOG):
    infile = resource_filename(Requirement.parse("molSimplify"),"tests/inputs/"+name+".in")
    newinfile = parse4testNoFF(infile,tmpdir)
    [passNumAtoms, passMLBL, passLG, passOG, pass_report]=[True,True,True,True,True]
    if newinfile != "":
        newname=jobname(newinfile)
        args =['main.py','-i', newinfile]
        startgen(args,False,False)
        myjobdir=jobdir(newinfile)
        output_xyz = myjobdir + '/'+ newname + '.xyz'
        output_report = myjobdir + '/'+ newname + '.report'
        ref_xyz = resource_filename(Requirement.parse("molSimplify"),"tests/refs/"+newname+".xyz")
        ref_report = resource_filename(Requirement.parse("molSimplify"),"tests/refs/"+newname+".report")
        print "Test input file: ", newinfile
        print "Test output files are generated in ",myjobdir
        print "Output xyz file: ", output_xyz
        pass_xyz=compareGeo(output_xyz,ref_xyz,threshMLBL,threshLG,threshOG)
        [passNumAtoms,passMLBL,passLG,passOG] = pass_xyz
        pass_report = compare_report_new(output_report,ref_report)
        print "Reference xyz file: ", ref_xyz
        print "Test report file: ", output_report
        print "Reference report file: ", ref_report
        print "Reference xyz status: ", pass_xyz
        print "Reference report status: ", pass_report
    return [passNumAtoms, passMLBL, passLG, passOG, pass_report]

def runtestMulti(tmpdir,name,threshMLBL,threshLG,threshOG):
    infile = resource_filename(Requirement.parse("molSimplify"),"tests/inputs/"+name+".in")
    newinfile = parse4test(infile,tmpdir,True)
    args =['main.py','-i', newinfile]
    #Need to make the ligand file visible to the input file
    startgen(args,False,False)
    myjobdir=jobdir(infile)+"/"
    print "Test input file: ", newinfile
    print "Test output files are generated in ",myjobdir
    refdir = resource_filename(Requirement.parse("molSimplify"),"tests/refs/"+name+"/")
    [passMultiFileCheck,myfiles]=checkMultiFileGen(myjobdir,refdir)
    pass_structures=[]
    if passMultiFileCheck==False:
        print "Test failed for checking number and names of generated files. Test ends"
    else:
        print "Checking each generated structure..."
        for f in myfiles:
            if ".xyz" in f:
                r=f.replace(".xyz",".report")
                output_xyz = output_xyz = myjobdir +f
                ref_xyz = refdir+f
                output_report = myjobdir+r
                ref_report = refdir+r
                print "Output xyz file: ", output_xyz
                print "Reference xyz file: ", ref_xyz
                print "Test report file: ", output_report
                print "Reference report file: ", ref_report
                pass_xyz=compareGeo(output_xyz,ref_xyz,threshMLBL,threshLG,threshOG)
                [passNumAtoms,passMLBL,passLG,passOG] = pass_xyz
                pass_report = compare_report_new(output_report,ref_report)
        pass_structures.append([f,passNumAtoms, passMLBL, passLG, passOG, pass_report])
    return [passMultiFileCheck,pass_structures]
