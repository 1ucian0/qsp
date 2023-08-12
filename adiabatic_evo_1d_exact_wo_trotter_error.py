#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
    

def make_mps_from_Q(L, Q, cyclic=False):
    Qs = [Q] * L
    if not cyclic:
        Qs[ 0] = np.squeeze(Qs[ 0][0, :, :])
        Qs[-1] = np.squeeze(Qs[-1][:, 0, :])
        
    mps = qtn.MatrixProductState(Qs, shape='lrp')
    mps = (mps^all).transpose(*('k0','k1','k2','k3','k4')).data.reshape(4**L)
    
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

    L = 5
    cyclic = False
    
    # gaps_all = []
    # thetas = []#list(np.linspace(0, 0.5, 21))#
    # thetas.append(np.arctan(1/3))
    # thetas = sorted(thetas)
        
    # for theta in thetas:
    #     H = build_aklt_hamiltonian_1d_sparse(theta, L, cyclic=False, sparse=True)
    #     energies = qu.eigvalsh(H, k=5)
        
    #     gaps = (energies[1]-energies[0], 
    #             energies[2]-energies[0], 
    #             energies[3]-energies[0], 
    #             energies[4]-energies[0])
        
    #     gaps_all.append(gaps)
        
    #     H_mpo = build_aklt_hamiltonian_1d_mpo(theta, L, cyclic=False, compress=True)
    #     dmrg = qtn.DMRG(H_mpo, bond_dims=[2]*24, cutoffs=1e-11)
    #     dmrg.solve()
    #     # print(theta, np.abs(sorted(energies)[0]-dmrg.energy), dmrg.energy)
            
    # # plt.plot(thetas, np.array(gaps_all),'.-')
    
    
    # singlet = np.sqrt(0.5) * np.array([[0., -1.], [1.,  0.]]) # vL p1
    # singlet_sqrt =  sp.linalg.sqrtm(singlet)
    
    # proj = np.zeros([2, 2, 3]) 
    # proj[0, 0, 0] = 1.  
    # proj[0, 1, 1] = 1./np.sqrt(2)  
    # proj[1, 0, 1] = 1./np.sqrt(2)
    # proj[1, 1, 2] = 1.  
    
    # A = ncon([proj, singlet], [(-1,2,-3),(2,-2)]) * np.sqrt(4./3.)
    
    # As = [A] * L
    # As[ 0] = np.squeeze(As[ 0][0, :, :])
    # As[-1] = np.squeeze(As[-1][:, 1, :])

    # mps = qtn.MatrixProductState(As, shape='lrp')
        
    # mps_adj = mps.H
    # mps_adj.align_(H_mpo, mps_adj)

    # exp_val = ((mps_adj & H_mpo & mps)^all)/((mps.H & mps)^all)
    # print( np.abs(exp_val - dmrg.energy), dmrg.energy)
    
    # ####################################    
    Q_aklt = make_1d_aklt_tensor()
    
    mps_aklt = make_mps_from_Q(L, Q_aklt, cyclic=cyclic)
    
    T, tau = 10, 0.02
    # s_func = lambda t,T=T: sin( half_pi*sin(half_pi*t/T)**2 )**2
    # s_func = lambda t,T=T: sin(half_pi*t/T)**2
    s_func = lambda t,T=T: t/T
    
    ts = np.arange(0, T+tau, tau)
    ss= [s_func(t) for t in ts]
    
    x = np.array(ts)
    fidelity_target  = np.zeros(len(ts)) + np.nan
    fidelity_current = np.zeros(len(ts)) + np.nan
        
    I = np.eye(4).reshape(2,2,4)
    gap = 1.0
    for t_it, t in enumerate(ts):
        s = ss[t_it]
        Q = (1 - s)*I + s*Q_aklt
        
        H, ham_term, ham_term_0, ham_term_n = constuct_parent_hamiltonian(L, Q, cyclic=cyclic)
        mps = make_mps_from_Q(L, Q, cyclic=cyclic)
        mps = mps/np.sqrt(np.conj(mps)@mps)
        
        ###########
        if t_it == 0: 
            psi =mps 
            continue
            
        I4 = np.eye(4)
        from numpy import kron as kr
        h = ham_term.reshape(16,16)
        h_0 = ham_term_0.reshape(16,16)
        h_n = ham_term_n.reshape(16,16)
        
        H_mpo = (kr(kr(kr(h_0, I4), I4), I4) + 
                       kr(kr(kr( I4,  h), I4), I4) + 
                       kr(kr(kr( I4, I4),  h), I4) + 
                       kr(kr(kr( I4, I4), I4), h_n))
        expm = sp.linalg.expm(-H_mpo*1j* tau*T )
    
        energy = np.conj(mps)@H_mpo@mps

        psi = expm@psi
        psi = psi/np.sqrt(np.conj(psi)@psi)
        
        overlap = (np.conj(mps)@psi)
        
        trotter_free_fidelity = np.abs(overlap)
        
        print(f"{t=:.2f}, {s=:.4f}, {np.abs(energy)=}") 
        print(f'{trotter_free_fidelity}, {fidelity_current[t_it]}, ')
        print("sanity:", np.sqrt(np.conj(mps)@mps), np.sqrt(np.conj(psi)@psi))
        
        # vals = sp.linalg.eigvalsh(H_mpo_array)
        # vals = sorted(vals)
        # gap = min(gap, np.abs(vals[4]-vals[0]))
        # print(":", sorted(vals)[:5], gap)
        print("")
        