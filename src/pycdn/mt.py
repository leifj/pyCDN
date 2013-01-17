#!/usr/bin/env python

# https://github.com/sangeeths/merkle-tree/blob/master/mt.py
import logging

import os
import hashlib

class MerkleTree:
    def __init__(self, root):
        self._linelength = 30
        self._root = root
        self._mt = {}
        self._hashlist = {}
        self._tophash = ''
        self.__MT__()

    def Line(self):
        logging.debug(self._linelength*'-')

    def PrintHashList(self):
        self.Line()
        for item, itemhash in self._hashlist.iteritems():
            logging.debug("%s %s" % (itemhash, item))
        self.Line()
        return

    def PrintMT(self, hash):
        value = self._mt[hash]
        item = value[0]
        child = value[1]
        logging.debug("%s %s" % (hash, item))
        if not child:
            return
        for itemhash, item in child.iteritems():
            logging.debug("    -> %s %s" % (itemhash, item))
        for itemhash, item in child.iteritems():
            self.PrintMT(itemhash)

    def MT(self):
        for node, hash in self._hashlist.iteritems():
            items = self.GetItems(node)
            value = [node]
            list = {}
            for item in items:
                if node == self._root:
                    list[self._hashlist[item]] = item
                else:
                    list[self._hashlist[os.path.join(node, item)]] = os.path.join(node, item)
            value.append(list)
            self._mt[hash] = value
        self._tophash = self._hashlist[self._root]

    def __MT__(self):
        self.HashList(self._root)
        #self.PrintHashList()
        self.MT()
        logging.debug("Merkle Tree for %s: " % self._root)
        self.PrintMT(self._tophash)
        self.Line()

    def sha2sum(self, data):
        m = hashlib.sha256()
        fn = os.path.join(self._root, data)
        if os.path.isfile(fn):
            try:
                f = file(fn, 'rb')
            except:
                raise ValueError('ERROR: unable to open %s' % fn)
            while True:
                d = f.read(8096)
                if not d:
                    break
                m.update(d)
            f.close()
        else:
            m.update(data)
        return m.hexdigest()

    def GetItems(self, directory):
        value = []
        if directory != self._root:
            directory = os.path.join(self._root, directory)
        if os.path.isdir(directory):
            items = os.listdir(directory)
            for item in items:
                value.append(item)
                #value.append(os.path.join(".", item))
            value.sort()
        return value

    def HashList(self, rootdir):
        self.HashListChild(rootdir)
        items = self.GetItems(rootdir)
        if not items:
            self._hashlist[rootdir] = ''
            return
        s = ''
        for subitem in items:
            s = s + self._hashlist[subitem]
        self._hashlist[rootdir] = self.sha2sum(s)

    def HashListChild(self, rootdir):
        items = self.GetItems(rootdir)
        if not items:
            self._hashlist[rootdir] = ''
            return
        for item in items:
            itemname = os.path.join(rootdir, item)
            if os.path.isdir(itemname) and not os.path.islink(itemname):
                self.HashListChild(item)
                subitems = self.GetItems(item)
                s = ''
                for subitem in subitems:
                    s = s + self._hashlist[os.path.join(item, subitem)]
                if rootdir == self._root:
                    self._hashlist[item] = self.sha2sum(s)
                else:
                    self._hashlist[itemname] = self.sha2sum(s)
            else:
                if rootdir == self._root:
                    self._hashlist[item] = self.sha2sum(item)
                else:
                    self._hashlist[itemname] = self.sha2sum(itemname)

def MTDiff(mt_a, a_tophash, mt_b, b_tophash):
    if a_tophash == b_tophash:
        logging.debug("Top hash is equal for %s and %s" % (mt_a._root, mt_b._root))
    else:
        a_value = mt_a._mt[a_tophash]
        a_child = a_value[1]    # retrive the child list for merkle tree a
        b_value = mt_b._mt[b_tophash]
        b_child = b_value[1]    # retrive the child list for merkle tree b

        for itemhash, item in a_child.iteritems():
            try:
                if b_child[itemhash] == item:
                    logging.debug("Info: SAME : %s" % item)
            except:
                logging.debug("Info: DIFFERENT : %s" % item)
                temp_value = mt_a._mt[itemhash]
                if len(temp_value[1]) > 0:      # check if this is a directory
                    diffhash = list(set(b_child.keys()) - set(a_child.keys()))
                    MTDiff(mt_a, itemhash, mt_b, diffhash[0])

def mtcmp(mt_a,mt_b):
    mt_a._tophash == mt_b._tophash

