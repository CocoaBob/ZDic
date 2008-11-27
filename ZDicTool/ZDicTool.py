#!/usr/bin/env python
# -*- coding: cp936 -*-
"""
ZDicת������
�ɽ�ZDic��׼�ı���ʽ��ά��XML��ʽת��ΪPDB�ʵ��ʽ
Ҳ�ɽ�PDB��ʽת��Ϊ�ı���ʽ
���ű�ʹ��GBK��ʽ����
"""

import os, sys, getopt, bz2, time, datetime, re, htmlentitydefs, bsddb
from struct import *
from xml.dom.minidom import parseString

PDBHeaderStructString = '>32shhLLLlll4s4sllH'           #PDB�ļ�ͷ
PDBHeaderStructLength = calcsize(PDBHeaderStructString) #PDB�ļ�ͷ����
padding = '\0\0'                                        #PDB�ļ�ͷ����

enc = sys.getfilesystemencoding()                       #ϵͳĬ�ϱ���
enc = 'gbk' if enc == 'UTF-8' else enc                  #�����UTF-8�����ΪGBK�����򲻱�

bsddb_opt = False                                       #Ĭ�ϲ�����bsddb����

replace_dic = {}                                        #������Ҫת����HTML�����ַ�����&nbsp; &lt;��
for name, codepoint in htmlentitydefs.name2codepoint.items():
    try:
        char = unichr(codepoint).encode(enc)            #enc�������ʾ��HTML����ʱ���Ž����滻
        replace_dic['&%s;' % name.lower()] = char
    except:
        pass

replace_ste = [('<hr>', '//STEHORIZONTALLINE//\\n'),
               ('<center>', '//STECENTERALIGN//'), ('</center>','\\n'),
               ('<u>', '//STEHYPERLINK='), ('</u>', '\1//'),
               ('<i>', '//STEBOLDFONT//'), ('</i>', '//STESTDFONT//'),
               ('<b>', '//STEBOLDFONT//'), ('</b>', '//STESTDFONT//'),
               ('<big>', '//STEBOLDFONT//'), ('</big>', '//STESTDFONT//')
              ] #���滻��STE��HTML���
    
removed_title = ['Help', 'Template', 'Image', 'Portal', 'Wikipedia', 'MediaWiki', 'WP'] #Ҫɾ����WIKI����
  
class ZDic:
    def __init__(self, compressFlag = 2, recordSize = 0x4000):
        "��ʼ��ZDic�࣬Ĭ��ΪZlibѹ����ʽ��16Kҳ���С"
        self.index = ''
        self.byteLen = []
        self.lenSec = ''
        self.creatorID = 'Kdic'
        self.pdbType = 'Dict'
        self.maxWordLen = 32
        self.recordSize = recordSize        
        self.compressFlag = compressFlag

    def ste(self,s):       
        for i, j in replace_ste: #�滻HTML���
            s = s.replace(i, j)     
        s = re.sub('\[\[([^\[/]*?)\]\]', '//STEHYPERLINK=\g<1>\1//', s) #��[[]]���STE������
        return s

    def unste(self,s):    
        return s.replace('//STEHYPERLINK=', '[[').replace('\1//', ']]')#��STE�����ӻ�ԭ��[[]]
    
    def fromPDB(self, path):
        "��PDB�ļ��ж�ȡ����"
        f = open(path, 'rb')
        self.header = f.read(PDBHeaderStructLength)
        self.pdbName = self.header[:32].rstrip('\0')
        self.bnum = unpack('>l',self.header[-4:])[0]
        startOffset = unpack('>L', f.read(4))[0]
        self.lines = {}
        for i in range(self.bnum - 1):
            f.seek(PDBHeaderStructLength + (i + 1) * 8)
            endOffset = unpack('>L', f.read(4))[0]
            f.seek(startOffset)
            if i == 0:
                f.seek(7, 1)
                self.compressFlag = ord(f.read(1))
            else:
                s = f.read(endOffset - startOffset)
                if self.compressFlag == 2:
                    s = s.decode('zlib')
                for line in s.rstrip().split('\n'):
                    k, v = line.split('\t', 1)
                    self.lines[k] = v                
            startOffset = endOffset
        f.seek(startOffset)
        s = f.read()
        if self.compressFlag == 2:
            s = s.decode('zlib')
        for line in s.rstrip().split('\n'):
            k, v = line.split('\t')
            self.lines[k] = v       
        f.close()

    def fromPath(self, path):
        files = [] #��������Ҫת�����ļ�       
        if os.path.isdir(path):
            files = glob.glob(os.path.join(path, '*.*'))
        else:
            files = [path] 
        self.lines = bsddb.btopen('tmp.db','c') if bsddb_opt else {}
        for path in files:
            ext=os.path.splitext(path)[1].lower()#��ȡ��׺��
            if ext in ['.xml', '.bz2']: #wiki xml
                def trim(s):
                    "����XML�ļ����"
                    s = s.encode(enc,'replace').replace('&amp;', '&') #��UTF8����ת��Ϊenc���룬�޷��������?����
                    for name, char in replace_dic.iteritems(): #�滻HTML�����ַ�
                        s = s.replace(name, char)
                    s = re.compile('(</?(p|font|br|tr|td|table|div|span|ref|small).*?>)|(\[\[[a-z]{2,3}(-[a-z]*?)?:[^\]]*?\]\])|(<!--.*?-->)',\
                                    re.I|re.DOTALL).sub('', s) #�滻����HTML���
                    s = re.sub('\n{3,}','\n\n',s).replace('\n', r'\n') #�������Ķ�����з��滻���������з�
                    return s
                def getData(page, title):
                    "��ȡ��Ӧ�ֶ�����"
                    try:
                        return trim(page.getElementsByTagName(title)[0].childNodes[0].data)
                    except:
                        return ''
                f = bz2.BZ2File(path) if ext == '.bz2' else open(path) #��ѹ�����߲�ѹ����ʽ����
                block = 1024*32 #ÿ�ζ���32K
                s = f.read(block)
                tmp = ''
                while 1:  
                    try:
                        a = s.index('<page>')
                        b = s.index('</page>',a + 6) + 7                #��ȡpage��
                        dom = parseString(s[a:b])
                        word, mean = getData(dom, 'title'), getData(dom, 'text')
                        if ((word in self.lines) and (mean[:9].lower()=='#redirect')) \
                           or ((':' in word) and word[:word.index(':')] in removed_title):#������ת������ظ�����������ĳЩ������
                            pass
                        elif word in self.lines:
                            self.lines[word]+=r'\n\n\n' + self.ste(mean) #�ظ��������ϲ���һ��
                        else:
                            self.lines[word]=self.ste(mean)
                        s=s[b:]
                    except:
                        tmp=f.read(block)
                        if tmp:
                            s+=tmp
                        else:
                            break
                f.close()
            elif ext == '.pdb': #PDB dic
                self.fromPDB(path) 
            else: #TXT dic
                f=open(path,'rU')
                for i in f:
                    i = i.rstrip().replace(' /// ', '\t', 1)    #���ʹ�� /// �ָ������滻��\t
                    if '\t' in i:
                        word, mean = i.split('\t', 1)           #�ָ����������
                        if word in self.lines:
                            self.lines[word]+=r'\n\n\n' + self.ste(mean) #�ظ��������ϲ���һ��
                        else:
                            self.lines[word] = self.ste(mean)   #STE����
        if bsddb_opt:
            self.lines.sync()
            self.lines.close()
            

    def resizeBlock(self):
        tmp=''
        first=''
        f=open('tmp.pdb','wb')
        if '' not in self.lines: #�ж����޴ʵ���Ϣ��û�����Զ����
            self.lines['']=self.ste('<b>Welcome to //STEPURPLEFONT//%s//STECURRENTFONT//!</b>\\n<b>Words count:</b> //STEBLUEFONT//%d//STECURRENTFONT//\\n<b>Made time:</b> //STEREDFONT//%s'%(self.pdbName,len(self.lines),time.strftime("%Y.%m.%d")))
        for word in sorted(self.lines.keys()):
            line = "%s\t%s\n"%(word,self.lines[word])
            if first=='':
                first=tmp
            if len(tmp)+len(line)<self.recordSize:
                tmp+=line
            else:
                if tmp:
                    self.compress(tmp,first.split('\t',1)[0],tmp.rsplit('\n',2)[-2].split('\t',1)[0],f)
                    tmp=''
                if len(line)>=self.recordSize:
                    index,line=line.split('\t',1)
                    i=0
                    while line:
                        tmpindex=i and "%s %d"%(index,i) or index
                        blen=self.recordSize-len(tmpindex)-3
                        if blen>len(line):
                            tmpline=line
                            line=''
                        else:
                            try:
                                breakindex = line.rindex('\\n', 0, blen)#�ڻ��з����ض�
                                tmpline = line[:breakindex]
                                line = line[breakindex+2:]
                            except:
                                tmpline = line[:blen]
                                line = line[blen:]
                        self.compress("%s\t%s\n"%(tmpindex,tmpline),tmpindex,tmpindex,f)
                        i+=1
                else:
                    tmp=line
                first=''
        if tmp:
            self.compress(tmp,first.split('\t',1)[0],line.rsplit('\n',2)[-2].split('\t',1)[0],f)
        f.close()

    def resizeBlockB(self):
        """bsddb version by emfox"""
        tmp=''
        first=''
        f=open('tmp.pdb','wb')
        dbf = bsddb.btopen('tmp.db','w')
        if '' not in dbf:
            dbf['']=self.ste('<b>Welcome to //STEPURPLEFONT//%s//STECURRENTFONT//!</b>\\n<b>Words count:</b> //STEBLUEFONT//%d//STECURRENTFONT//\\n<b>Made time:</b> //STEREDFONT//%s'%(self.pdbName,len(dbf),time.strftime("%Y.%m.%d")))
        word,mean = dbf.first()
        while 1:
            line = "%s\t%s\n"%(word,mean)
            if first=='':
                first=tmp
            if len(tmp+line)<self.recordSize:
                tmp+=line
            else:
                if tmp:
                    self.compress(tmp,first.split('\t',1)[0],tmp.rsplit('\n',2)[-2].split('\t',1)[0],f)
                    tmp=''
                if len(line)>=self.recordSize:
                    index,line=line.split('\t',1)
                    i=0
                    while line:
                        tmpindex=i and "%s %d"%(index,i) or index
                        blen=self.recordSize-len(tmpindex)-3
                        if blen>len(line):
                            tmpline=line
                            line=''
                        else:
                            """if '//STE' in line[blen-40:blen+4]: #split form //STE
                                steindex=line[blen-40:blen+4].index('//STE')
                                blen=blen-40+steindex
                            elif '\\n' == line[blen-1:blen+1]: # split from \n
                                blen=blen-1
                            tmpline=line[:blen]
                            line=line[blen:]
                            try:
                                tmpline.decode('gbk')
                            except:
                                line=tmpline[-1]+line
                                tmpline=tmpline[:-1]"""
                            try:
                                breakindex = line.rindex('\\n', 0, blen)#�ڻ��з����ض�
                                tmpline=line[:breakindex]
                                line=line[breakindex+2:]
                            except:
                                tmpline=line[:blen]
                                line=line[blen:]                            
                        self.compress("%s\t%s\n"%(tmpindex,tmpline),tmpindex,tmpindex,f)
                        i+=1
                else:
                    tmp=line
                first=''
            try:
                word,mean = dbf.next()
            except:
                break
        if tmp:
            self.compress(tmp,first.split('\t',1)[0],line.rsplit('\n',2)[-2].split('\t',1)[0],f)
        dbf.close()
        f.close()
        os.remove('tmp.db')
            
    def compress(self,block,first,last,f):
        block=block.encode('zlib')
        f.write(block)
        l=len(block)
        self.byteLen.append(l)
        self.lenSec+=pack('>H',l)
        self.index+="%s\0%s\0"%(first[:self.maxWordLen],last[:self.maxWordLen])         
            
    def packPalmDate(self, variable=None):
        PILOT_TIME_DELTA = 2082844800L        
        variable = variable or datetime.datetime.now()
        return int(time.mktime(variable.timetuple())+PILOT_TIME_DELTA)
        
    def packPDBHeader(self):
        return pack(PDBHeaderStructString,
                    self.pdbName,0,0,
                    self.packPalmDate(),0,0,0,0,0,
                    self.pdbType,self.creatorID,0,0,self.bnum
                )

    def toPDB(self,path):
        self.bnum=len(self.byteLen)
        self.index=pack('>I2H8x',1,self.bnum,2)+self.lenSec+ self.index
        del self.lenSec     
        #record index   
        self.byteLen.insert(0,len(self.index))
        self.bnum+=1
        towrite=self.packPDBHeader()
        offset=PDBHeaderStructLength + 8 * self.bnum +len(padding)
        uid=0x406F8000      
        for i in self.byteLen:
            towrite+=pack('>2L', offset, uid) 
            offset+=i
            uid+=1
        del offset,uid,i,self.byteLen
        towrite+=padding
        f=open(path,'wb')
        #header and index
        f.write(towrite+self.index)
        del towrite,self.index
        block=1024*1024*10 #
        tmp=open('tmp.pdb','rb')
        while 1:
            cont=tmp.read(block)
            if cont:
                f.write(cont)
            else:
                break
        tmp.close()        
        os.remove('tmp.pdb')
        f.close()

    def p2t(self, path, patho):
        "pdb=>txt"
        f = open(path, 'rb')        
        f.seek(PDBHeaderStructLength - 4)
        self.bnum= unpack('>l',f.read(4))[0]
        firstOffset = unpack('>L', f.read(4))[0]
        f.seek(4, 1)
        startOffset = unpack('>L', f.read(4))[0]
        f.seek(firstOffset + 7)
        self.compressFlag = ord(f.read(1))
        if self.compressFlag == 1:
            f.close()
            os.system('DeKDic.exe %s' % path)
            os.system('ren %s.tab %s' %(path, patho))
        else:
            t = open(patho, 'wb')
            for i in range(1, self.bnum - 1):
                f.seek(PDBHeaderStructLength + (i + 1) * 8)
                endOffset = unpack('>L',f.read(4))[0]
                f.seek(startOffset)
                t.write(self.unste(f.read(endOffset - startOffset).decode('zlib')))
                startOffset = endOffset
            f.seek(startOffset)
            t.write(self.unste(f.read().decode('zlib')))
            t.close()
            f.close()

    def toTXT(self, patho):
        "��lines���򱣴���txt�ļ��У����ڱ༭�޸�"
        f = open( patho, 'w')
        for word, mean in sorted(self.lines.iteritems()):
            print >>f, "%s\t%s" % (word, self.unste(mean))
        f.close()        

def log(msg):
    """��ӡ��־"""
    print '[%s]%s'%(time.strftime('%X'), msg)
    
if __name__ == '__main__':    
    opts, argv = getopt.getopt(sys.argv[1:], 'bt')
    if len(argv) != 2:
        log('�﷨�� [-t] [-b] �ļ���1 �ļ���2') #��������ʱ�����﷨��ʾ
    else:
        pathi, patho = argv
        try:
            s = time.time() #��¼��ʼʱ��
            log('�����ļ�...')
            app = ZDic()    #��ʹ��ZDic���ݽṹ
            app.pdbName = os.path.splitext(os.path.basename(patho))[0]
            if ('-t', '') in opts: #-t������ת��Ϊ�ı��ļ�
                if pathi.endswith('pdb'):
                    app.p2t(pathi, patho)
                else:
                    app.fromPath(pathi)
                    log('�����ļ�...')
                    app.toTXT(patho)
            else:
                bsddb_opt = ('-b', '') in opts #-b������ʹ��bsddb����С�ڴ棬�ϴ��ļ����ϳ�ʱ��
                app.fromPath(pathi)
                log('�����ļ�...')
                if bsddb_opt:
                    app.resizeBlockB()
                else:
                    app.resizeBlock()
                log('�����ļ�...')
                app.toPDB(patho)                
            cost = time.time() - s #���㻨��ʱ��
            log('�ɹ�������ʱ %dh%dm%ds ��' % (cost/3600, cost%3600/60, cost%60))
        except:
            log('����')
            raise
        


