## @file nn_prep.py
#  Helper routines for ANN integration
#  
#   Written by JP Janet for HJK Group
#  
#  Dpt of Chemical Engineering, MIT

from molSimplify.Scripts.geometry import *
from molSimplify.Scripts.io import *
from molSimplify.Scripts.nn_prep import spin_classify
from molSimplify.Informatics.decoration_manager import*
from molSimplify.Classes.globalvars import *
from molSimplify.Informatics.graph_analyze import *
from molSimplify.Informatics.RACassemble import *
from molSimplify.python_nn.tf_ANN import *
import time
from sets import Set
#import numpy
#import openbabel

## wrapper to get AN predictions from a known mol3D()
## generally unsfae
def invoke_ANNs_from_mol3d(mol,oxidation_state,alpha=0.2,debug=False):
    # check input
    if not oxidation_state == 2 and not oxidation_state == 3:
        print('Error, oxidation state must be 2 or 3')
        return False
    
    # find the metal from RACs 
    metal = mol.getAtom(mol.findMetal()[0]).symbol()
    ox_modifier = {metal:oxidation_state}
    # get RACs
    descriptor_names, descriptors = get_descriptor_vector(mol,ox_modifier=ox_modifier)
    # get one-hot-encoding (OHE)
    descriptor_names,descriptors = create_OHE(descriptor_names,descriptors, metal,oxidation_state)
    # set exchange fraction
    descriptor_names += ['alpha']
    descriptors += [alpha]

    # call ANN for splitting
    split, latent_split = ANN_supervisor('split',descriptors,descriptor_names,debug)

    # call ANN for bond lenghts
    if oxidation_state == 2:
        r_ls, latent_r_ls = ANN_supervisor('ls_ii',descriptors,descriptor_names,debug)
        r_hs, latent_r_hs = ANN_supervisor('hs_ii',descriptors,descriptor_names,debug)
    elif oxidation_state == 3:
        r_ls, latent_r_ls = ANN_supervisor('ls_iii',descriptors,descriptor_names,debug)
        r_hs, latent_r_hs = ANN_supervisor('hs_iii',descriptors,descriptor_names,debug)

    # ANN distance for splitting
    split_dist = find_true_min_eu_dist("split",descriptors,descriptor_names)

    # compile results and return
    results_dictionary = {"ls_bl":r_ls,
                         "hs_bl":r_hs,
                         "split":split,
                         "distance":split_dist }
    return(results_dictionary)
            

def tf_check_ligands(ligs,batlist,dents,tcats,occs,debug):
    ## tests if ligand combination
    ## is compatiable with the ANN
    # INPUT:
    #   - ligs:  list of mol3D class, ligands
    #   - batlist: list of int, occupations 
    #   - dents: list of int, denticity
    #   - tcats: list of int/bool
    # OUTPUT:
    #   - valid: bool
    ## tcats controls
    ## manual overide
    ## of connection atoms

    n_ligs = len(ligs)
    if debug:
        print('nligs '  + str(n_ligs))
        print('ligs '  + str(ligs))
        print('occs in function  '  + str(occs))
        print('tcats in function  '  + str(tcats))
    unique_ligands = []
    axial_ind_list =[]
    equitorial_ind_list =[]
    axial_ligs = []
    equitorial_ligs = []
    ax_dent = 0 
    eq_dent  =0
    eq_ligs = []
    eq_tcat = False
    ax_tcat = False
    triple_bidentate = False
    ax_occs = []
    eq_occs = []
    valid = True
    if  (set(dents) == set([2])):
        print('triple bidentate case')
        triple_bidentate = True
        unique_ligs = []
        ucats = []
        unique_dict = {}
        if not(n_ligs) == 3:
                ## something unexpected happened!
                valid = False 
        for i in range(0,n_ligs):
            this_bat = batlist[i]
            this_lig = ligs[i]
            this_dent = dents[i]
            this_occs = occs[i]
            ## mulitple points
            if not (this_lig in unique_ligs):
                unique_ligs.append(this_lig)
                ucats.append(tcats[i])
                unique_dict.update({this_lig: 1})
            elif (this_lig in unique_ligs):
                unique_dict.update({this_lig:unique_dict[this_lig]+1})
                   
        if len(unique_ligs) == 1:
            axial_ligs.append(ligs[0])
            ax_dent  = 2
            ax_tcat = tcats[0]
            ax_occs.append(1)
            equitorial_ligs.append(ligs[0])
            eq_dent  = 2
            eq_tcat = tcats[0]
            eq_occs.append(2)
        elif len(unique_ligs) == 2:
            for key in unique_dict.keys():
                if unique_dict[key] == 1:
                    axial_ligs.append(key)
                    ax_dent = 2
                    ax_occs.append(1)
                    ax_tcat = tcats[ligs.index(key)]
                elif unique_dict[key] == 2:
                    equitorial_ligs.append(key)
                    eq_dent = 2
                    eq_occs.append(2)
                    eq_tcat = tcats[ligs.index(key)]
        else:
            valid = False
    else:
        for i in range(0,n_ligs):
            
            
            this_bat = batlist[i]
            if debug:
                print('iteration  '+ str(i))
                print('this bat ' + str(this_bat) + ' from ' +  str(batlist))
            this_lig = ligs[i]
            this_dent = dents[i]
            this_occ = occs[i]
#            print(this_bat,this_lig,this_dent)
            ## mulitple points
            if len(this_bat) == 1:
                if (5 in this_bat) or (6 in this_bat):
                    
                    if not (this_lig in axial_ligs):
                        if debug:
                            print('adding ' + str(this_lig) + ' to axial')
                        axial_ligs.append(this_lig)
                        ax_dent = this_dent
                        if this_lig not in ['x','oxo','hydroxyl']:
                            ax_tcat = tcats[i]
                        ax_occs.append(occs[i])
                    else:
                        ax_occs[axial_ligs.index(this_lig)] += 1
                else:                    
                    if not (this_lig in equitorial_ligs):
                        equitorial_ligs.append(this_lig)
                        eq_dent = this_dent
                        eq_tcat = tcats[i]
                        eq_occs.append(occs[i])
                    else:
                        eq_occs[equitorial_ligs.index(this_lig)] += 1
                        
            else:
                if not (this_lig in equitorial_ligs):
                        equitorial_ligs.append(this_lig)
                        eq_dent = this_dent
                        eq_tcat = tcats[i]
                        eq_occs.append(occs[i])
                else:
                        eq_occs[equitorial_ligs.index(this_lig)] += 1

    if  (len(axial_ligs) > 2):
        print('axial lig error : ',axial_ligs,ax_dent,ax_tcat,ax_occs)
        valid = False
    if debug:
        print('eq occupations  ' + str(eq_occs))
        print('eq dent   ' + str(eq_dent))
    if not (4.0/(float(eq_dent)*sum(eq_occs)) == 1):
        print('equitorial ligs error: ',equitorial_ligs,eq_dent,eq_tcat)
        valid = False
    if valid: # get the index position in ligs
        axial_ind_list = [ligs.index(ax_lig) for ax_lig in axial_ligs]
        equitorial_ind_list = [ligs.index(eq_lig) for eq_lig in equitorial_ligs]
        
    return valid,axial_ligs,equitorial_ligs,ax_dent,eq_dent,ax_tcat,eq_tcat,axial_ind_list,equitorial_ind_list,ax_occs,eq_occs

def check_metal(metal,oxidation_state):
    supported_metal_dict = {"fe":[2,3],"mn":[2,3],"cr":[2,3],
                            "co":[2,3],"ni":[2]}
    romans={'I':'1','II':'2','III':'3','IV':'4','V':'5','VI':'6'}
    if oxidation_state  in romans.keys():
        oxidation_state= romans[oxidation_state]
    outcome = False
    if metal in supported_metal_dict.keys():
#        print('metal in',supported_metal_dict[metal])
        if int(oxidation_state) in supported_metal_dict[metal]:
            outcome = True
    return outcome,oxidation_state




def tf_ANN_preproc(args,ligs,occs,dents,batslist,tcats,licores):
    ### prepares and runs ANN calculation

    current_time =  time.time()
    start_time = current_time
    last_time = current_time

    ######################
    ANN_reason = False # holder for reason to reject ANN call
    ANN_attributes = dict()
    ######################

    r = 0
    emsg = list()
    valid = True 
    catalysis = False
    metal = args.core
    this_metal = metal.lower()
    if len(this_metal) >2 :
        this_metal = this_metal[0:2]
    newligs = []
    newcats = []
    newdents = []
    newoccs = []
    newdecs = [False]*6
    newdec_inds = [[]]*6
    ANN_trust = False
    count = -1
    for i,lig in enumerate(ligs):
        this_occ = occs[i]
        if args.debug:
            print('working on lig: ' + str(lig))
            print('occ is  ' + str(this_occ)) 
        for j in range(0,int(this_occ)):
            count += 1
            newligs.append(lig)
            newdents.append(dents[i])
            newcats.append(tcats[i])
            newoccs.append(1)
            if args.decoration:               
                newdecs[count] = (args.decoration[i])
                newdec_inds[count] = (args.decoration_index[i])

    ligs = newligs  
    dents = newdents
    tcats = newcats 
    occs = newoccs
    if args.debug:
        print('tf_nn has finisihed prepping ligands')  
   
    if not args.geometry == "oct":
        emsg.append("[ANN] Geometry is not supported at this time, MUST give -geometry = oct")
        valid = False 
        ANN_reason = 'geometry not oct'
    if not args.oxstate:
        emsg.append("\n oxidation state must be given")
        valid = False
        ANN_reason = 'oxstate not given'
    if valid:
        oxidation_state = args.oxstate
        valid, oxidation_state = check_metal(this_metal,oxidation_state)
        if int(oxidation_state) in [3, 4, 5]:
            catalytic_moieties = ['oxo','x','hydroxyl','[O--]','[OH-]']
            if args.debug:
                print('the ligands are',ligs)
                print(set(ligs).intersection(set(catalytic_moieties)))
            if len(set(ligs).intersection(set(catalytic_moieties))) > 0:
                catalysis = True
        ## generate key in descriptor space
        ox = int(oxidation_state)
        spin = args.spin
        if args.debug:
            print('metal is '+ str(this_metal))
            print('metal validity',valid)
    if not valid and not catalysis:
            emsg.append("\n Oxidation state not available for this metal")
            ANN_reason = 'ox state not avail for metal'
    if valid:
        high_spin,spin_ops = spin_classify(this_metal,spin,ox)
    if not valid and not catalysis:
            emsg.append("\n this spin state not available for this metal")
            ANN_reason = 'spin state not availble for metal'
    if emsg:
        print(str(" ".join( ["ANN messages:"] +   [str(i) for i in emsg] )))

    
    current_time =  time.time()
    metal_check_time  = current_time - last_time
    last_time = current_time
    if args.debug:
        print('checking metal/ox took  ' +  "{0:.2f}".format(metal_check_time) + ' seconds' )

    if valid or catalysis:
        valid,axial_ligs,equitorial_ligs,ax_dent,eq_dent,ax_tcat,eq_tcat,axial_ind_list,equitorial_ind_list,ax_occs,eq_occs = tf_check_ligands(ligs,batslist,dents,tcats,occs,args.debug)

        if args.debug:
            print("ligand validity is  "+str(valid))
            print('Occs',occs)
            print('Ligands',ligs)
            print('Dents',dents)
            print('Bats (backbone atoms)',batslist)
            print('lig validity',valid)
            print('ax ligs',axial_ligs)
            print('eq ligs',equitorial_ligs)
            print('spin is',spin)
        if catalysis:
            valid = False
    if (not valid) and (not catalysis):
        ANN_reason  = 'found incorrect ligand symmetry'
    elif not valid and catalysis:
        if args.debug:
            print('tf_nn detects catalytic')
        ANN_reason = 'catalytic structure presented'

    
    ## placeholder for metal    
    metal_mol = mol3D()
    metal_mol.addAtom(atom3D(metal))     

    if valid or catalysis:
            if args.debug:
                print('loading axial ligands')
            ax_ligands_list = list()
            eq_ligands_list = list()
            for ii, axl in enumerate(axial_ligs):
                ax_lig3D,r_emsg = lig_load(axl,licores) # load ligand
                if r_emsg:
                    emsg += r_emsg
                if ax_tcat:
                    ax_lig3D.cat = ax_tcat
                    if args.debug:
                        print('custom ax connect atom given (0-ind) '+str(ax_tcat))
                this_lig  = ligand(mol3D(), [],ax_dent)
                this_lig.mol = ax_lig3D
                
                 ## check decoration index
                if newdecs:
                        if newdecs[axial_ind_list[ii]]:
                            print('decorating ' + str(axl) + ' with ' +str(newdecs[axial_ind_list[ii]]) + ' at sites '  + str(newdec_inds[axial_ind_list[ii]]))
                            ax_lig3D = decorate_ligand(args,axl,newdecs[axial_ind_list[ii]],newdec_inds[axial_ind_list[ii]])
                ax_lig3D.convert2mol3D() ## mol3D representation of ligand
                for jj in range(0,ax_occs[ii]):
                    ax_ligands_list.append(this_lig)
            if args.debug:
                print('ax_ligands_list:')
                print(ax_ligands_list)
                print([h.mol.cat  for h in ax_ligands_list])
            
            if args.debug:
                print('loading equitorial ligands')
            for ii, eql in enumerate(equitorial_ligs):
                eq_lig3D,r_emsg = lig_load(eql,licores) # load ligand
                if r_emsg:
                        emsg += r_emsg
                if eq_tcat:
                    eq_lig3D.cat = eq_tcat
                    if args.debug:
                        print('custom eq connect atom given (0-ind) '+str(eq_tcat))
                this_lig  = ligand(mol3D(), [],eq_dent)
                this_lig.mol = eq_lig3D

                if newdecs:
                    if newdecs[equitorial_ind_list[ii]]:
                            print('decorating ' + str(eql) + ' with ' +str(newdecs[equitorial_ind_list[ii]]) + ' at sites '  + str(newdec_inds[equitorial_ind_list[ii]]))
                            eq_lig3D = decorate_ligand(args,eql,newdecs[equitorial_ind_list[ii]],
                                                                newdec_inds[equitorial_ind_list[ii]])
        
                eq_lig3D.convert2mol3D() ## mol3D representation of ligand
                for jj in range(0,eq_occs[ii]):
                    eq_ligands_list.append(this_lig)
            if args.debug:
                print('eq_ligands_list:')
                print(eq_ligands_list)
                    
                current_time =  time.time()
                ligand_check_time  = current_time - last_time
                last_time = current_time
                print('checking ligs took ' +  "{0:.2f}".format(ligand_check_time) + ' seconds')
            
            
            ## make description of complex 
            custom_ligand_dict = {"eq_ligand_list":eq_ligands_list,
                                  "ax_ligand_list":ax_ligands_list,
                                  "eq_con_int_list":[h.mol.cat  for h in eq_ligands_list],
                                  "ax_con_int_list":[h.mol.cat  for h in ax_ligands_list]}
            
            ox_modifier = {metal:ox}
            this_complex = assemble_connectivity_from_parts(metal_mol,custom_ligand_dict)
            
    
            if args.debug:
                print('custom_ligand_dict is : ')                      
                print(custom_ligand_dict)                      
            
        

    
    if args.debug:
        print('finished checking ligands, valid is '+str(valid))
        print('assembling RAC custom ligand configuration dictionary')
        
    if valid:
        ## build RACs without geo
        con_mat  = this_complex.graph  
        descriptor_names, descriptors = get_descriptor_vector(this_complex,custom_ligand_dict,ox_modifier)
        
        ## get one-hot-encoding (OHE)
        descriptor_names,descriptors = create_OHE(descriptor_names,descriptors, metal,oxidation_state)
        
        # get alpha
        alpha = 0.2 # default for B3LYP
        if args.exchange:
            try:
                if float(args.exchange) > 1:
                    alpha = float(args.exchange)/100 # if given as %
                elif float(args.exchange) <= 1:
                    alpha = float(args.exchange)
            except:
                print('cannot cast exchange argument as a float, using 20%')
        descriptor_names += ['alpha']
        descriptors += [alpha]
        descriptor_names += ['ox']
        descriptors += [ox]
        descriptor_names += ['spin']
        descriptors += [spin]
        if args.debug:
            current_time =  time.time()
            rac_check_time  = current_time - last_time
            last_time = current_time
            print('getting RACs took ' +  "{0:.2f}".format(rac_check_time) + ' seconds')


        ## get spin splitting:
        split, latent_split = ANN_supervisor('split',descriptors,descriptor_names,args.debug)
        if args.debug:
            current_time =  time.time()
            split_ANN_time  = current_time - last_time
            last_time = current_time
            print('split ANN took ' +  "{0:.2f}".format(split_ANN_time) + ' seconds')
        
        ## get bond lengths:
        if oxidation_state == '2':
            r_ls, latent_r_ls  = ANN_supervisor('ls_ii',descriptors,descriptor_names,args.debug)
            r_hs, latent_r_hs  = ANN_supervisor('hs_ii',descriptors,descriptor_names,args.debug)
        elif oxidation_state == '3':
            r_ls, latent_r_ls  = ANN_supervisor('ls_iii',descriptors,descriptor_names,args.debug)
            r_hs, latent_r_hs  = ANN_supervisor('hs_iii',descriptors,descriptor_names,args.debug)
        if not high_spin:
            r = r_ls[0]
        else:
            r = r_hs[0]
            
        if args.debug:
            current_time =  time.time()
            GEO_ANN_time  = current_time - last_time
            last_time = current_time
            print('GEO ANN took ' +  "{0:.2f}".format(GEO_ANN_time)+ ' seconds')

        homo, latent_homo = ANN_supervisor('homo',descriptors,descriptor_names,args.debug)
        if args.debug:
            current_time =  time.time()
            homo_ANN_time  = current_time - last_time
            last_time = current_time
            print('homo ANN took ' +  "{0:.2f}".format(homo_ANN_time) + ' seconds')

        gap, latent_gap = ANN_supervisor('gap',descriptors,descriptor_names,args.debug)
        if args.debug:
            current_time =  time.time()
            gap_ANN_time  = current_time - last_time
            last_time = current_time
            print('gap ANN took ' +  "{0:.2f}".format(gap_ANN_time) + ' seconds')

        ## get minimum distance to train (for splitting)
        
        split_dist = find_true_min_eu_dist("split",descriptors,descriptor_names)
        if args.debug:
            current_time =  time.time()
            min_dist_time  = current_time - last_time
            last_time = current_time
            print('min dist took ' +  "{0:.2f}".format(min_dist_time)+ ' seconds')
        
        homo_dist = find_true_min_eu_dist("homo",descriptors,descriptor_names)
        homo_dist = find_ANN_latent_dist("homo",latent_homo,args.debug)
        if args.debug:
            current_time =  time.time()
            min_dist_time  = current_time - last_time
            last_time = current_time
            print('min HOMO dist took ' +  "{0:.2f}".format(min_dist_time)+ ' seconds')

        gap_dist = find_true_min_eu_dist("gap",descriptors,descriptor_names)
        gap_dist = find_ANN_latent_dist("gap",latent_gap,args.debug)
        if args.debug:
            current_time =  time.time()
            min_dist_time  = current_time - last_time
            last_time = current_time
            print('min GAP dist took ' +  "{0:.2f}".format(min_dist_time)+ ' seconds')

        ## save attributes for return
        ANN_attributes.update({'split':split[0][0]})
        ANN_attributes.update({'split_dist':split_dist} )
        ANN_attributes.update({'This spin':spin})
        if split[0][0] < 0 and (abs(split[0]) > 5):
            ANN_attributes.update({'ANN_ground_state':spin_ops[1]})
        elif split[0][0] > 0 and (abs(split[0]) > 5):
            ANN_attributes.update({'ANN_ground_state':spin_ops[0]})
        else:
            ANN_attributes.update({'ANN_ground_state':'dgen ' + str(spin_ops)})

        ANN_attributes.update({'homo':homo[0][0]})
        ANN_attributes.update({'gap':gap[0][0]})
        ANN_attributes.update({'homo_dist':homo_dist})
        ANN_attributes.update({'gap_dist':gap_dist}) 
        
        ## now that we have bond predictions, we need to map these
        ## back to a length of equal size as the original ligand request
        ## in order for molSimplify to understand if
        ANN_bondl  = len(ligs)*[False]
        added = 0
        for ii,eql in enumerate(equitorial_ind_list):
            for jj in range(0,eq_occs[ii]):
                ANN_bondl[added] = r[2]
                added += 1
                

        for ii,axl in enumerate(axial_ind_list):
            if args.debug:
                print(ii,axl,added,ax_occs)
            for jj in range(0,ax_occs[ii]):
                if args.debug:
                    print(jj,axl,added,r[ii])
                ANN_bondl[added] = r[ii]
                added += 1

        ANN_attributes.update({'ANN_bondl':4*[r[2]]+[r[0],r[1]]})
        
        HOMO_ANN_trust = 'not set'
        HOMO_ANN_trust_message = ""
        if float(homo_dist)< 3: #Not quite sure if this should be divided by 3 or not, since RAC-155 descriptors
            HOMO_ANN_trust_message = 'ANN results should be trustworthy for this complex '
            HOMO_ANN_trust = 'high'
        elif float(homo_dist)< 5:
            HOMO_ANN_trust_message = 'ANN results are probably useful for this complex '
            HOMO_ANN_trust  = 'medium'
        elif float(homo_dist)<= 10:
            HOMO_ANN_trust_message = 'ANN results are fairly far from training data, be cautious '
            HOMO_ANN_trust = 'low'
        elif float(homo_dist)> 10:
            HOMO_ANN_trust_message = 'ANN results are too far from training data, be cautious '
            HOMO_ANN_trust = 'very low'
        ANN_attributes.update({'homo_trust':HOMO_ANN_trust})
        ANN_attributes.update({'gap_trust':HOMO_ANN_trust})

        ANN_trust = 'not set'
        ANN_trust_message = ""
        if float(split_dist/3)< 0.25:
            ANN_trust_message = 'ANN results should be trustworthy for this complex '
            ANN_trust = 'high'
        elif float(split_dist/3)< 0.75:
            ANN_trust_message = 'ANN results are probably useful for this complex '
            ANN_trust  = 'medium'
        elif float(split_dist/3)< 1.0:
            ANN_trust_message = 'ANN results are fairly far from training data, be cautious '
            ANN_trust = 'low'
        elif float(split_dist/3)> 1.0:
            ANN_trust_message = 'ANN results are too far from training data, be cautious '
            ANN_trust = 'very low'
        ANN_attributes.update({'split_trust':ANN_trust})
        
        ## print text to std out
        print("******************************************************************")
        print("************** ANN is engaged and advising on spin ***************")
        print("************** and metal-ligand bond distances    ****************")
        print("******************************************************************")
        if high_spin:
            print('You have selected a high-spin state, s = ' + str(spin))
        else:
            print('You have selected a low-spin state, s = ' + str(spin))
        ## report to stdout
        if split[0] < 0 and not high_spin:
            if abs(split[0]) > 5:
                print('warning, ANN predicts a high spin ground state for this complex')
            else:
                print('warning, ANN predicts a near degenerate ground state for this complex')
        elif split[0] >= 0 and high_spin:
            if abs(split[0]) > 5:
                print('warning, ANN predicts a low spin ground state for this complex')
            else:
                print('warning, ANN predicts a near degenerate ground state for this complex')
        print('delta is' ,split[0],' spin is ',high_spin)
        print("ANN predicts a spin splitting (HS - LS) of " + "{0:.2f}".format(float(split[0])) + ' kcal/mol at '+"{0:.0f}".format(100*alpha) + '% HFX')
        print('ANN low spin bond length (ax1/ax2/eq) is predicted to be: '+" /".join(["{0:.2f}".format(float(i)) for i in r_ls[0]]) + ' angstrom')
        print('ANN high spin bond length (ax1/ax2/eq) is predicted to be: '+" /".join(["{0:.2f}".format(float(i)) for i in r_hs[0]]) + ' angstrom')
        print('distance to splitting energy training data is ' + "{0:.2f}".format(split_dist) )
        print(ANN_trust_message)
        print("ANN predicts a HOMO value of " + "{0:.2f}".format(float(homo[0])) + ' eV at '+"{0:.0f}".format(100*alpha) + '% HFX')
        print("ANN predicts a LUMO-HOMO energetic gap value of " + "{0:.2f}".format(float(gap[0])) + ' eV at '+"{0:.0f}".format(100*alpha) + '% HFX')
        print(HOMO_ANN_trust_message)
        print('distance to HOMO training data is ' + "{0:.2f}".format(homo_dist) )
        print('distance to GAP training data is ' + "{0:.2f}".format(gap_dist) )
        print("*******************************************************************")
        print("************** ANN complete, saved in record file *****************")
        print("*******************************************************************")
        from keras import backend as K
        K.clear_session() #This is done to get rid of the attribute error that is a bug in tensorflow.
        
    if valid:    
        current_time =  time.time()
        total_ANN_time  = current_time - start_time
        last_time = current_time
        print('Total ML functions took ' +  "{0:.2f}".format(total_ANN_time) + ' seconds') 

    if catalysis:
        ## build RACs without geo
        con_mat  = this_complex.graph  
        descriptor_names, descriptors = get_descriptor_vector(this_complex,custom_ligand_dict,ox_modifier)
        # get alpha
        alpha = 20 # default for B3LYP
        if args.exchange:
            try:
                if float(args.exchange) < 1:
                    alpha = float(args.exchange)*100 # if given as %
                elif float(args.exchange) >= 1:
                    alpha = float(args.exchange)
            except:
                print('cannot case exchange argument as a float, using 20%')
        descriptor_names += ['alpha']
        descriptors += [alpha]
        descriptor_names += ['ox']
        descriptors += [ox]
        descriptor_names += ['spin']
        descriptors += [spin]
        if args.debug:
            current_time =  time.time()
            rac_check_time  = current_time - last_time
            last_time = current_time
            print('getting RACs took ' +  "{0:.2f}".format(rac_check_time) + ' seconds')
        oxo, latent_oxo = ANN_supervisor('oxo',descriptors,descriptor_names,args.debug,args.debug)
        if args.debug:
            current_time =  time.time()
            split_ANN_time  = current_time - last_time
            last_time = current_time
            print('oxo ANN took ' +  "{0:.2f}".format(split_ANN_time) + ' seconds')
        oxo_dist = find_ANN_latent_dist("oxo",latent_oxo,args.debug)
        if args.debug:
            current_time =  time.time()
            min_dist_time  = current_time - last_time
            last_time = current_time
            print('min oxo dist took ' +  "{0:.2f}".format(min_dist_time)+ ' seconds')
        ANN_attributes.update({'oxo':oxo[0][0]})
        ANN_attributes.update({'oxo_dist':oxo_dist})

        hat, latent_hat = ANN_supervisor('hat',descriptors,descriptor_names,args.debug)
        if args.debug:
            current_time =  time.time()
            split_ANN_time  = current_time - last_time
            last_time = current_time
            print('HAT ANN took ' +  "{0:.2f}".format(split_ANN_time) + ' seconds')

        hat_dist = find_ANN_latent_dist("hat",latent_hat,args.debug)
        if args.debug:
            current_time =  time.time()
            min_dist_time  = current_time - last_time
            last_time = current_time
            print('min hat dist took ' +  "{0:.2f}".format(min_dist_time)+ ' seconds')

        ANN_attributes.update({'hat':hat[0][0]})
        ANN_attributes.update({'hat_dist':hat_dist})

        Oxo_ANN_trust = 'not set'
        Oxo_ANN_trust_message = ""
        if float(oxo_dist)< 3: #Not quite sure if this should be divided by 3 or not, since RAC-155 descriptors
            Oxo_ANN_trust_message = 'Oxo ANN results should be trustworthy for this complex '
            Oxo_ANN_trust = 'high'
        elif float(oxo_dist)< 5:
            Oxo_ANN_trust_message = 'Oxo ANN results are probably useful for this complex '
            Oxo_ANN_trust  = 'medium'
        elif float(oxo_dist)<= 10:
            Oxo_ANN_trust_message = 'Oxo ANN results are fairly far from training data, be cautious '
            Oxo_ANN_trust = 'low'
        elif float(oxo_dist)> 10:
            Oxo_ANN_trust_message = 'Oxo ANN results are too far from training data, be cautious '
            Oxo_ANN_trust = 'very low'
        ANN_attributes.update({'oxo_trust':Oxo_ANN_trust})


        HAT_ANN_trust = 'not set'
        HAT_ANN_trust_message = ""
        if float(hat_dist)< 3: #Not quite sure if this should be divided by 3 or not, since RAC-155 descriptors
            HAT_ANN_trust_message = 'HAT ANN results should be trustworthy for this complex '
            HAT_ANN_trust = 'high'
        elif float(hat_dist)< 5:
            HAT_ANN_trust_message = 'HAT ANN results are probably useful for this complex '
            HAT_ANN_trust  = 'medium'
        elif float(hat_dist)<= 10:
            HAT_ANN_trust_message = 'HAT ANN results are fairly far from training data, be cautious '
            HAT_ANN_trust = 'low'
        elif float(hat_dist)> 10:
            HAT_ANN_trust_message = 'HAT ANN results are too far from training data, be cautious '
            HAT_ANN_trust = 'very low'
        ANN_attributes.update({'hat_trust':HAT_ANN_trust})
        print("*******************************************************************")
        print("**************       CATALYTIC ANN ACTIVATED!      ****************")
        print("*********** Currently advising on Oxo and HAT energies ************")
        print("*******************************************************************")
        print("ANN predicts a oxo formation energy of " + "{0:.2f}".format(float(oxo[0])) + ' kcal/mol at '+"{0:.2f}".format(alpha) + '% HFX')
        print(Oxo_ANN_trust_message)
        print('Distance to oxo training data in the latent space is ' + "{0:.2f}".format(oxo_dist) )
        print("ANN predicts a HAT energy of " + "{0:.2f}".format(float(hat[0])) + ' kcal/mol at '+"{0:.2f}".format(alpha) + '% HFX')
        print(HAT_ANN_trust_message)
        print('Distance to HAT training data in the latent space is ' + "{0:.2f}".format(hat_dist) )
        print("*******************************************************************")
        print("************** ANN complete, saved in record file *****************")
        print("*******************************************************************")
        from keras import backend as K
        K.clear_session() #This is done to get rid of the attribute error that is a bug in tensorflow.

    if catalysis:    
        current_time =  time.time()
        total_ANN_time  = current_time - start_time
        last_time = current_time
        print('Total Catalysis ML functions took ' +  "{0:.2f}".format(total_ANN_time) + ' seconds')

    if not valid and not ANN_reason and not catalysis:
        ANN_reason = ' uncaught rejection (see sdout/stderr)'

    return valid,ANN_reason,ANN_attributes, catalysis

        
            


    if False:
        ## test Euclidean norm to training data distance
        train_dist,best_row = find_eu_dist(nn_excitation)
        ANN_trust = max(0.01,1.0-train_dist)
        
        ANN_attributes.update({'ANN_closest_train':best_row} )

        print(' with closest training row ' + best_row[:-2] + ' at  ' + str(best_row[-2:]) + '% HFX')

    
       
        ### use ANN to predict fucntional sensitivty
        HFX_slope = 0 
        HFX_slope = get_slope(slope_excitation)
        print('Predicted HFX exchange sensitivity is : '+"{0:.2f}".format(float(HFX_slope)) + ' kcal/HFX')
        ANN_attributes.update({'ANN_slope':HFX_slope})
