#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Sep 22 12:12:48 2021
@author: mohsin
"""
import numpy as np
from scipy.linalg import null_space
from quimb.tensor import Tensor, MatrixProductState, TensorNetwork

from ncon import ncon



dtype = 'complex128'

def generate_unitaries(mps_in, d=2):
    mps = mps_in.copy(deep=True)

    Gs_lst = []
    submps_indices = get_submps_indices(mps)
    for start_indx, end_indx in submps_indices:
        # print(f'now [{(start_indx)}, {(end_indx)}]:')

        # construct the unitaries
        Gs, isoms, kernels = [], [], []
        for it in range(start_indx, end_indx+1):
            if (it == (end_indx)):
                if ((end_indx-start_indx)==0):
                    G = np.zeros((d,d), dtype=dtype)
                    G[0,:] = mps[it].data.reshape((1,-1))
                    G[1,:] = null_space(mps[it].data.copy().reshape((1, -1)).conj()).reshape((1, -1))

                else:
                    G = mps[it].data

                G = Tensor(G.reshape((d,d)).T, inds=('v', 'p'), tags={'G'}) # .T at the end is useful for the application of unitaries as quantum circuit
                
                Gs.append(G)
                
                ############
                isoms.append([])
                kernels.append([])

            elif (it!=start_indx):

                G = np.zeros((d,d,d,d), dtype=dtype)
                G[0,:,:,:]=mps[it].data
                kernel = null_space(mps[it].data.copy().reshape((d, -1)).conj())
                kernel = kernel*(1/np.exp(1j*np.angle(kernel[0,:])))
                G[1:d, :, :, :] = kernel.reshape((d, d, d, d-1)).transpose((3, 2, 0, 1))

                G = G.transpose((0,1,3,2))
                # now the indices of G are ordered as G(L,B,T,R)

                G = G.transpose((1,0,3,2))
                # now the indices of G are ordered as G(B,L,R,T)

                G = Tensor(G.reshape((d**2,d**2)).T, inds=['L', 'R'], tags={'G'})   # .T at the end is useful for the application of unitaries as quantum circuit
                Gs.append(G)
                
                ############
                G = G.data.T.reshape((d,d,d,d))
                kernel = G[:,1,:,:].reshape(2,4).T
                kernel = kernel*(1/np.exp(1j*np.angle(kernel[0,:])))
                [eigvals, eigvecs] = np.linalg.eigh(kernel@np.conj(kernel.T))
                isom = eigvecs[:, np.where(np.abs(eigvals) > 1e-12)].reshape(4, -1)
                isoms.append(isom)
                kernels.append(kernel)

            elif (it == start_indx):

                G = np.zeros((d, d, d, d), dtype=dtype)
                G[0, 0, :, :] = mps[it].data.reshape((d, -1))
                kernel = null_space(mps[it].data.copy().reshape((1, -1)).conj())
                
                for i in range(d):
                    for j in range(d):
                        if (i==0 and j==0):
                            continue;
                        ind = i*d+j
                        G[i,j,:,:]= kernel[:,ind-1].reshape((d, d))

                G = G.transpose((0,1,3,2))
                # now the indices of G are ordered as G(L,B,T,R)

                G = G.transpose((1,0,3,2))
                # now the indices of G are ordered as G(B,L,R,T)

                G = Tensor(G.reshape((d**2,d**2)).T, inds=['L','R'], tags={'G'})    # .T at the end is useful for the application of unitaries as quantum circuit
                Gs.append(G)
                
                ############
                G = G.data.T.reshape((d,d,d,d))
                kernel = G[:,1,:,:].reshape(2,4).T
                kernel = np.c_[G[1,0,:,:].reshape(1,4).T, kernel]
                [eigvals, eigvecs] = np.linalg.eigh(kernel@np.conj(kernel.T))
                isom = eigvecs[:, np.where(np.abs(eigvals) > 1e-12)].reshape(4, -1)
                isoms.append(isom)
                kernels.append(kernel)
                
        Gs_lst.append([start_indx, end_indx, Gs, isoms, kernels])

    return Gs_lst
    
def apply_unitary_layer_on_wfn(Gs_lst, wfn):
    
    A = wfn.copy(deep=True)
    # wfn_clone = wfn.copy(deep=True)

    for start_indx, end_indx, Gs, _, _ in Gs_lst:
        for it in range(start_indx, end_indx+1):
            if (it==end_indx):
                # wfn_clone.gate_(Gs[it-start_indx].data, where=[it], tags='U', propagate_tags='sites')
                
                
                A.gate_(Gs[it-start_indx].data, where=[it])
                loc = np.where([isinstance(A[jt],tuple) for jt in range(A.L)])[0][0]
                A.contract_ind(A[loc][-1].inds[-1])
                # A.right_canonize()
                


            else:
                # wfn_clone.gate_(Gs[it-start_indx].data, where=[it,it+1], tags='U', propagate_tags='sites')
                
                A=A.gate_split(Gs[it-start_indx].data, where=[it,it+1])                
                # A.right_canonize()

    A.permute_arrays(shape='lpr')
    # print(np.conj(wfn_clone.to_dense().T)@A.to_dense())
    A.compress('right')

    return A#wfn_clone

def apply_unitary_layer_on_wfn_usg_ncon(Gs_lst, wfn):
    
    zero_wf = wfn.reshape(1,-1)
    start_indx, end_indx, Gs, _, _  = Gs_lst[0]
    L = end_indx+1
    wfn = wfn.reshape([2]*L)
    
    lft_inds = (-(np.arange(L)+1+L)).tolist()
    
    u = np.eye(2**L, dtype=np.complex128).reshape([2]*(2*L))
    for it in range(L):
        if (it==end_indx):
            inds = -(np.arange(L)+1)
            inds[it] = -inds[it]
            
            G = Gs[it-start_indx].data
            wfn = ncon([wfn, G],(inds.tolist(), [-inds[it], inds[it]]))
            u = ncon([u, G],(inds.tolist()+lft_inds, [-inds[it], inds[it]]))
            
        else:
            inds = -(np.arange(L)+1)
            inds[it] = -inds[it]
            inds[it+1] = -inds[it+1]
            G = Gs[it-start_indx].data.reshape((2,2,2,2))
            
            wfn = ncon([wfn, G],(inds.tolist(), [-inds[it], -inds[it+1], inds[it], inds[it+1]]))
    
            u = ncon([u, G],( inds.tolist()+lft_inds, [-inds[it], -inds[it+1], inds[it], inds[it+1]]))

    u = u.reshape([2**L]*2)
    a = ncon([zero_wf.reshape(-1,1), u],([1,-1],[-2,1]))
    wfn = MatrixProductState.from_dense(wfn, dims=[2]*L)
    return wfn


def generate_unitary_from_G_lst(Gs_lst):
    
    start_indx, end_indx, Gs, _, _  = Gs_lst[0]
    L = end_indx+1
    lft_inds = (-(np.arange(L)+1+L)).tolist()
    
    u = np.eye(2**L, dtype=np.complex128).reshape([2]*(2*L))
    for it in range(L):
        if (it==end_indx):
            inds = -(np.arange(L)+1)
            inds[it] = -inds[it]
            
            G = Gs[it-start_indx].data
            u = ncon([u, G],(inds.tolist()+lft_inds, [-inds[it], inds[it]]))
        else:
            inds = -(np.arange(L)+1)
            inds[it] = -inds[it]
            inds[it+1] = -inds[it+1]
            G = Gs[it-start_indx].data.reshape((2,2,2,2))
            
            u = ncon([u, G],( inds.tolist()+lft_inds, [-inds[it], -inds[it+1], inds[it], inds[it+1]]))

    u = u.reshape([2**L]*2)
    
    return u


def apply_unitary_layers_on_wfn(unitary_layers, wfn):

    for it in reversed(range(len(unitary_layers))):
        wfn = apply_unitary_layer_on_wfn(unitary_layers[it], wfn)#MatrixProductState.from_dense((apply_unitary_layer_on_wfn(unitary_layers[it], wfn)).to_dense(), dims = [2]*wfn.L)
        
        # wfn = apply_unitary_layer_on_wfn(unitary_layers[it], wfn)
        # wfn = wfn.contract_compressed(optimize=None, max_bond=24)
        
    return wfn


# def apply_inverse_multi_unitary_layer_on_wfn(pre_factors, unitaries, psi):
#     dims = psi.shape
#     psi_it = MatrixProductState.from_dense(np.ones(shape=(prod(dims),1)), dims=dims)*0

#     for pre_factor, Gs_lst in zip(pre_factors, unitaries):
#         psi_it = MatrixProductState.from_dense(psi_it.to_dense() + (1/pre_factor)*apply_inverse_unitary_layer_on_wfn(Gs_lst, psi).to_dense(), dims=dims)

#     return psi_it


def apply_inverse_unitary_layer_on_wfn(Gs_lst, wfn):    
    A = wfn.copy(deep=True)
    # wfn_clone = wfn.copy(deep=True)

    for start_indx, end_indx, Gs, _, _ in Gs_lst:
        # u_tags = [f'U{i}' for i in reversed(range(L))]
        for it in list(reversed(range(start_indx, end_indx+1))):
            if (it==end_indx):
                # wfn_clone.gate_(Gs[it-start_indx].data.conj().T, where=[it], tags='U', propagate_tags='sites')
                
                A.gate_(Gs[it-start_indx].data.conj().T, where=[it])
                loc = np.where([isinstance(A[jt],tuple) for jt in range(A.L)])[0][0]
                A.contract_ind(A[loc][-1].inds[-1])
                # A.right_canonize()
                
            else:
                # wfn_clone.gate_(Gs[it-start_indx].data.conj().T, where=[it,it+1], tags='U', propagate_tags='sites')
                
                A=A.gate_split(Gs[it-start_indx].data.conj().T, where=[it,it+1])                
                # A.right_canonize()
                
    A.permute_arrays(shape='lpr')
    # print(np.conj(wfn_clone.to_dense().T)@A.to_dense())
    return A


def get_submps_indices(mps):
    submps_indices = []
    if (mps.L==1):
        submps_indices.append([0,0])

    else:
        for it in range(mps.L):
            DL, DR = 1, 1

            if (it==0):
                _, DR = mps[it].shape

            elif (it==(mps.L-1)):
                DL,_ = mps[it].shape

            else:
                DL, _, DR = mps[it].shape

            if (DL<2 and DR<2):
                submps_indices.append([it,it])

            elif (DL<2 and DR>=2):
                temp = it

            elif (DL>=2 and DR<2):
                submps_indices.append([temp,it])

    return submps_indices