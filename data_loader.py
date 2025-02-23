import warnings
import pickle as pkl
import sys, os

import scipy.sparse as sp
import networkx as nx
import torch
import numpy as np

# from sklearn import datasets
# from sklearn.preprocessing import LabelBinarizer, scale
# from sklearn.model_selection import train_test_split
# from ogb.nodeproppred import DglNodePropPredDataset
# import copy

from utils import sparse_mx_to_torch_sparse_tensor #, dgl_graph_to_torch_sparse

warnings.simplefilter("ignore")


def parse_index_file(filename):
    """Parse index file."""
    index = []
    for line in open(filename):
        index.append(int(line.strip()))
    return index

#使得該id的值為1，其餘為0，增加Mask
def sample_mask(idx, l):
    """Create mask."""
    mask = np.zeros(l)
    mask[idx] = 1
    return np.array(mask, dtype=np.bool)


def load_citation_network(dataset_str, sparse=None):
    names = ['x', 'y', 'tx', 'ty', 'allx', 'ally', 'graph']  #citation network的檔案副檔名
    objects = []
    for i in range(len(names)):
        with open("data/ind.{}.{}".format(dataset_str, names[i]), 'rb') as f:
            if sys.version_info > (3, 0):
                objects.append(pkl.load(f, encoding='latin1'))
            else:
                objects.append(pkl.load(f))
                
    # index檔案獨立input
    x, y, tx, ty, allx, ally, graph = tuple(objects)
    test_idx_reorder = parse_index_file("data/ind.{}.test.index".format(dataset_str))  # type = list
    test_idx_range = np.sort(test_idx_reorder)  # type = array

    if dataset_str == 'citeseer':
        # Fix citeseer dataset (there are some isolated nodes in the graph)
        # Find isolated nodes, add them as zero-vecs into the right position
        test_idx_range_full = range(min(test_idx_reorder), max(test_idx_reorder) + 1)
        tx_extended = sp.lil_matrix((len(test_idx_range_full), x.shape[1]))
        tx_extended[test_idx_range - min(test_idx_range), :] = tx
        tx = tx_extended
        ty_extended = np.zeros((len(test_idx_range_full), y.shape[1]))
        ty_extended[test_idx_range - min(test_idx_range), :] = ty
        ty = ty_extended

    # sp.vstack(a,b) = 將a,b直接疊起來
    # 在tolil( )形成List of Lists format    
    features = sp.vstack((allx, tx)).tolil()
    features[test_idx_reorder, :] = features[test_idx_range, :]  #為什麼要做這步?

    # nx = networkx module 縮寫
    # from_dict_of_lists( )：Returns a graph from a dictionary of lists.
    # adjacency_matrix( )：Returns adjacency matrix of G
    # todense()：轉換回普通矩陣
    adj = nx.adjacency_matrix(nx.from_dict_of_lists(graph))
    if not sparse:
        adj = np.array(adj.todense(),dtype='float32')
    else:
        adj = sparse_mx_to_torch_sparse_tensor(adj)  #轉換成tensor

    labels = np.vstack((ally, ty))
    labels[test_idx_reorder, :] = labels[test_idx_range, :]
    idx_test = test_idx_range.tolist()
    idx_train = range(len(y))
    idx_val = range(len(y), len(y) + 500)

    train_mask = sample_mask(idx_train, labels.shape[0])
    val_mask = sample_mask(idx_val, labels.shape[0])
    test_mask = sample_mask(idx_test, labels.shape[0])

    features = torch.FloatTensor(features.todense())  #torch.FloatTensor是32位浮點數類型，torch.LongTensor是64位整數型
    labels = torch.LongTensor(labels)
    train_mask = torch.BoolTensor(train_mask)
    val_mask = torch.BoolTensor(val_mask)
    test_mask = torch.BoolTensor(test_mask)

    nfeats = features.shape[1]
    for i in range(labels.shape[0]):   # labels 一個表示屬於這個類別
        sum_ = torch.sum(labels[i])
        if sum_ != 1:  # sum不等於1，表示被歸類在兩種類別中，或是錯誤
            labels[i] = torch.tensor([1, 0, 0, 0, 0, 0])
    
    # labels == 1 ->每一個點各自去判斷是否值為1，labels[0] ==1 >>> tensor([False, False, False,  True, False, False, False])
    # Tensor.nonzero()  ->找出其中不屬於0的那個位置
    # torch.max() ->找出裡面值最大的類別 ， Tensor.item()取出裡面的值
    labels = (labels == 1).nonzero()[:, 1]  
    nclasses = torch.max(labels).item() + 1
        
    
    return features, nfeats, labels, nclasses, train_mask, val_mask, test_mask, adj
    #features:訓練特徵, nfeats:特徵數量, labels:標籤, nclasses:共有幾個類別, train_mask, val_mask, test_mask->遮罩們, adj:鄰接矩陣

def load_data(args):
    return load_citation_network(args.dataset, args.sparse)
