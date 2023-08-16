#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pickle as pkl
import numpy as np
import scipy as sp

from numpy import sin
half_pi = np.pi/2

from ncon import ncon 

from matplotlib import pyplot as plt

import quimb.tensor as qtn
import quimb as qu


def build_aklt_hamiltonian_1d_sparse(theta, L, cyclic=False, sparse=True):
    dims = [3] * L
    
    sites = tuple(range(L))
    def gen_pairs():
        for j in range(L if cyclic else L-1):
            a, b = j, (j+1) % L
            yield (a,b)
    
    pairs = gen_pairs()
    
    cos_theta, sin_theta = np.cos(theta), np.sin(theta)
    
    def aklt_interaction(pair):
        
        X = qu.spin_operator('X', sparse=True, S=1)
        Y = qu.spin_operator('Y', sparse=True, S=1)
        Z = qu.spin_operator('Z', sparse=True, S=1)
        
        ss = (qu.ikron([1 * X, X], dims, inds=pair) + 
              qu.ikron([1 * Y, Y], dims, inds=pair) + 
              qu.ikron([1 * Z, Z], dims, inds=pair))
        
        term = cos_theta*ss + sin_theta *(ss@ss)
        
        return term
    
    # combine all terms
    all_terms = map(aklt_interaction, pairs)
    H = sum(all_terms)

    # can improve speed of e.g. eigensolving if known to be real
    if qu.isreal(H):
        H = H.real

    if not sparse:
        H = qu.qarray(H.A)

    return H


def build_aklt_hamiltonian_1d_mpo(theta, L, cyclic=False, compress=True):
    S=1
    H = qtn.SpinHam1D(S=S, cyclic=cyclic)

    x = qu.spin_operator("x", S=S)
    y = qu.spin_operator("y", S=S)
    z = qu.spin_operator("z", S=S)

    H += np.cos(theta), x, x
    H += np.cos(theta), y, y
    H += np.cos(theta), z, z

    H += np.sin(theta), x@x, x@x
    H += np.sin(theta), x@y, x@y
    H += np.sin(theta), x@z, x@z
    H += np.sin(theta), y@x, y@x
    H += np.sin(theta), y@y, y@y
    H += np.sin(theta), y@z, y@z
    H += np.sin(theta), z@x, z@x
    H += np.sin(theta), z@y, z@y
    H += np.sin(theta), z@z, z@z
    
    H_mpo = H.build_mpo(L)
    if compress is True:
        H_mpo.compress(cutoff=1e-12, cutoff_mode="rel" if cyclic else "sum2")
    return H_mpo


def make_hamiltonian_mpo(L, ham_term, ham_term_0, ham_term_n, cyclic, compress=False):
    H = qtn.SpinHam1D(S=3/2, cyclic=cyclic)
    
    for site_indx in range((L-1)):
        if site_indx==0:
            u,s,v = sp.linalg.svd(ham_term_0.transpose([0,2,1,3]).reshape(16,16))
            
        elif site_indx==(L-1-1):
            u,s,v = sp.linalg.svd(ham_term_n.transpose([0,2,1,3]).reshape(16,16))
            
        else:
            u,s,v = sp.linalg.svd(ham_term.transpose([0,2,1,3]).reshape(16,16))
            
        for it in range(s.shape[0]):
            if np.abs(s[it])>1e-12:
                H[site_indx, site_indx+1] += s[it], qu.qu(u[:,it].reshape(4,4)), qu.qu(v[it,:].reshape(4,4))
    
    
    H_local_ham1D = H.build_local_ham(L)
    H_mpo = H.build_mpo(L, )
    if compress is True:
        H_mpo.compress(cutoff=1e-12, cutoff_mode="rel" if cyclic else "sum2")
    
    return H_mpo, H_local_ham1D


def make_evolution_mpo(L, ham_term, ham_term_0, ham_term_n, cyclic, compress=False):
    hamiltonian = [ham_term]*(L-1)
    hamiltonian[0] = ham_term_0
    hamiltonian[L-2] = ham_term_n
    
    
    # mpo for applying gates from left to right
    mpo_tens = [[] for _ in range(L)]    
    for site_indx in range((L-1)):  # run over all the interactions
        evo_op = sp.linalg.expm(hamiltonian[site_indx].reshape(16,16)*-1j*tau/2*T).reshape((4,4,4,4))
        u,s,v = sp.linalg.svd(evo_op.transpose([0,2,1,3]).reshape(16,16))
        v = np.diag(s)@v
        
        u = u.reshape(4,4,-1)
        v = v.reshape((-1,4,4))
        
        mpo_tens[site_indx].append(u)   
        mpo_tens[site_indx+1].append(v) # first comes v and then u


    for indx in range(L):   # run over all the sites
        if indx==0:
            mpo_tens[0] = mpo_tens[0][0].transpose((2,0,1))
            
        elif indx==(L-1):
            mpo_tens[L-1] = mpo_tens[L-1][0]
            
        else:
            v,u = mpo_tens[indx][0], mpo_tens[indx][1] 
            mpo_tens[indx] = ncon((v,u),([-1, -3, 1],[1,-4,-2]))
            
    mpo_1 = qtn.MatrixProductOperator(mpo_tens, 'lrdu')    
        
    
    # mpo for applying gates from right to left
    mpo_tens = [[] for _ in range(L)]    
    for site_indx in reversed(range((L-1))):  # run over all the interactions
        evo_op = sp.linalg.expm(hamiltonian[site_indx].reshape(16,16)*-1j*tau/2*T).reshape((4,4,4,4))
        u,s,v = sp.linalg.svd(evo_op.transpose([0,2,1,3]).reshape(16,16))
        v = np.diag(s)@v
        
        u = u.reshape(4,4,-1)
        v = v.reshape((-1,4,4))
        
        mpo_tens[site_indx].append(u)   # first comes u and then u
        mpo_tens[site_indx+1].append(v) 
    
    
    for indx in range(L):   # run over all the sites
        if indx==0:
            mpo_tens[0] = mpo_tens[0][0].transpose((2,0,1))
            
        elif indx==(L-1):
            mpo_tens[L-1] = mpo_tens[L-1][0]
            
        else:
            u,v = mpo_tens[indx][0], mpo_tens[indx][1] 
            mpo_tens[indx] = ncon((u,v),([-3, 1, -2],[-1, 1,-4]))
            
    mpo_2 = qtn.MatrixProductOperator(mpo_tens, 'lrdu')
        
    mpo_1.compress(cutoff=1e-12, cutoff_mode="rel" if cyclic else "sum2")
    mpo_2.compress(cutoff=1e-12, cutoff_mode="rel" if cyclic else "sum2")
    
    return mpo_1, mpo_2


def constuct_parent_hamiltonian(L, Q, cyclic=False):
    kernel = sp.linalg.null_space(ncon([Q,Q],[(-1,1,-3),(1,-2,-4)]).reshape(4,4**2))
    ham_term = 0.    
    for it in range(kernel.shape[1]):
        v = kernel[:,it]
        ham_term += ncon((np.conj(v),v),([-1],[-2]))    
    ham_term = ham_term.reshape((4,4,4,4))
    
    
    Q_0 = (Q[0:1, :, :])
    Q_n = (Q[:, 0:1, :])
    
    kernel = sp.linalg.null_space(ncon([Q_0,Q],[(-1,1,-3),(1,-2,-4)]).reshape(2,4**2))
    ham_term_0 = 0.    
    for it in range(kernel.shape[1]):
        v = kernel[:,it]
        ham_term_0 += ncon((np.conj(v),v),([-1],[-2]))    
    ham_term_0 = ham_term_0.reshape((4,4,4,4))
    
    kernel = sp.linalg.null_space(ncon([Q,Q_n],[(-1,1,-3),(1,-2,-4)]).reshape(2,4**2))
    ham_term_n = 0.    
    for it in range(kernel.shape[1]):
        v = kernel[:,it]
        ham_term_n += ncon((np.conj(v),v),([-1],[-2]))    
    ham_term_n = ham_term_n.reshape((4,4,4,4))
    
    if not cyclic:
        H = [qtn.Tensor(ham_term, inds=(f'k{i}',f'k{i+1}', f'b{i}',f'b{i+1}')) for i in range(L-1)]
        H[ 0] = qtn.Tensor(ham_term_0, inds=(f'k{0}',f'k{1}', f'b{0}',f'b{1}'))
        H[-1] = qtn.Tensor(ham_term_n, inds=(f'k{L-2}',f'k{L-1}', f'b{L-2}',f'b{L-1}')) 
        
    return H, ham_term, ham_term_0, ham_term_n
    

def calculate_energy_from_parent_hamiltonian(L, mps, H):
    energy = 0.
    for i in range(L-1):
        mps_adj = mps.reindex({f'k{indx}':f'b{indx}' for indx in set([int(indx[1:]) for indx in H[i].inds])}).H
        energy += ((mps_adj & H[i] & mps )^all)/((mps.H & mps)^all)        
    return energy


def calculate_energy_from_parent_hamiltonian_mpo(mps, H_mpo):
    mps_adj = mps.H
    mps_adj.align_(H_mpo, mps_adj)
    exp_val = ((mps_adj & H_mpo & mps)^all)/((mps.H & mps)^all)   
    return exp_val


def make_mps_from_Q(L, Q, cyclic=False):
    Qs = [Q] * L
    if not cyclic:
        Qs[ 0] = np.squeeze(Qs[ 0][0, :, :])
        Qs[-1] = np.squeeze(Qs[-1][:, 0, :])
        
    mps = qtn.MatrixProductState(Qs, shape='lrp')
    return mps


def make_1d_aklt_tensor():
    # ####################################
    Q_aklt = np.zeros([2,2, 2,2]) 
    Q_aklt[0,0, 0,0] = 1.  
    
    Q_aklt[0,1, 0,1] = 1./(2)  
    Q_aklt[0,1, 1,0] = 1./(2)  
    
    Q_aklt[1,0, 0,1] = 1./(2)
    Q_aklt[1,0, 1,0] = 1./(2)
    
    Q_aklt[1,1, 1,1] = 1.  
    Q_aklt = Q_aklt.reshape((2,2,4))
    
    isometry = np.zeros((2,2,3))
    isometry[0,0, 0] = 1
    
    isometry[0,1, 1] = 1./np.sqrt(2)
    isometry[1,0, 1] = 1./np.sqrt(2)
    
    isometry[1,1, 2] = 1
    isometry = isometry.reshape(4,3)
    # Q = ncon([Q, isometry], [(-1,-2,3),(3,-3)])
    
    ####################################
    singlet = np.sqrt(0.5) * np.array([[0., -1.], [1.,  0.]]) # vL p1
    singlet_sqrt =  sp.linalg.sqrtm(singlet)
    Q_aklt = ncon([Q_aklt, singlet_sqrt,singlet_sqrt], [(1,2,-3),(-1,1),(2,-2)])
        
    return Q_aklt


if __name__ == "__main__":    

    L = 32
    cyclic = False
    
    ####################################    
    Q_aklt = make_1d_aklt_tensor()
    
    mps_aklt = make_mps_from_Q(L, Q_aklt, cyclic=cyclic)
    mps_aklt = mps_aklt/np.abs(np.sqrt( (mps_aklt.H & mps_aklt)^all ))
    
    T, tau = 6, 0.04
    s_func = lambda t,T=T: sin( half_pi*sin(half_pi*t/T)**2 )**2
    # s_func = lambda t,T=T: sin(half_pi*t/T)**2
    # s_func = lambda t,T=T: t/T
    
    ts = np.arange(0, T+tau, tau)
    
    x = np.array(ts)
    fidelity_target  = np.zeros(len(ts)) + np.nan
    fidelity_current = np.zeros(len(ts)) + np.nan 
        
    I = np.eye(4).reshape(2,2,4)
    for t_it, t in enumerate(ts):
        s = s_func(t)
        Q = (1 - s)*I + s*Q_aklt
        
        H, ham_term, ham_term_0, ham_term_n = constuct_parent_hamiltonian(L, Q, cyclic=cyclic)
        H_mpo, H_local_ham1D = make_hamiltonian_mpo(L, ham_term, ham_term_0, ham_term_n, cyclic, compress=False)
        
        mpo_1, mpo_2 = make_evolution_mpo(L, ham_term, ham_term_0, ham_term_n, cyclic, compress=False)
        
        mps = make_mps_from_Q(L, Q, cyclic=cyclic)
        
        norm_mps = np.sqrt((mps.H & mps)^all)
        
        # energy = calculate_energy_from_parent_hamiltonian(L, mps, H)
        energy = calculate_energy_from_parent_hamiltonian_mpo(mps, H_mpo)
        print(f"{t=:.2f}, {s=:.4f}, {np.abs(energy)=}") 
                
        if t_it==0:
            psi = mps.copy()
            
        psi = mpo_1.apply(psi)
        psi.compress(max_bond=2)  

        psi = mpo_2.apply(psi)
        psi.compress(max_bond=2)  
        
        psi.right_canonize(normalize=True)
        norm_psi = np.sqrt((psi.H & psi)^all)
            
        # tebd = qtn.TEBD(psi, H_local_ham1D)
        # # tebd.split_opts['cutoff'] = 1e-12
        
        # for psi_it in tebd.at_times([tau], tol=1e-12):
        #     psi = psi_it
            
        norm_psi = np.sqrt((psi.H & psi)^all)
        energy = calculate_energy_from_parent_hamiltonian_mpo(psi, H_mpo)
        print(f"{t=:.2f}, {s=:.4f}, {np.abs(energy)=}\n") 
        
        fidelity_target[t_it]  = np.abs( ((mps_aklt.H & psi)^all)/(norm_psi) )
        fidelity_current[t_it] = np.abs( ((mps.H & psi)^all)/(norm_mps*norm_psi) )
        print(f"{t=:.2f}, {s=:.4f}, \n{np.abs(energy)=}, \n{fidelity_target[t_it]=}, \n{fidelity_current[t_it]=}")
        print("")
        
        
        # plt.plot(ts, fidelity_current, '.-')
        # plt.pause(0.05)

        # ###### sanity check for the parent hamiltonian only for L=5
        # I4 = qu.eye(4)
        # term = qu.qu(H[2].data).reshape((16,16))
        # H_full = ((term & I4 & I4 & I4) + 
        #           (I4 & term & I4 & I4) + 
        #           (I4 & I4 & term & I4) + 
        #           (I4 & I4 & I4 & term))
    
        # ## make it cyclic
        # if cyclic:
        #     I4 = np.array(I4)
        #     term = np.array(term)        
        #     H_full = H_full + ncon( (I4,I4,I4,term.reshape((4,4,4,4))), ((-2,-7),(-3,-8),(-4,-9),(-5,-1,-10,-6)) ).reshape((4**L,4**L))
        # vals = sp.linalg.eigvals(H_full)
        # print(sorted(np.real(vals))[:5])
        # # print(sp.linalg.eigvals(Q.reshape(4,4)))
        # print('\n')
        
    ###################################   