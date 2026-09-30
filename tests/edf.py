"""Minimal EDF reader (ResMed STR.edf) used by the local SD-card regression test."""
import struct,datetime as dt
def read_edf(path):
    b=open(path,'rb').read()
    h=lambda a,n: b[a:a+n].decode('latin1').strip()
    ns=int(h(252,4)); nrec=int(h(236,8)); dur=float(h(244,8))
    start=dt.datetime.strptime(h(168,8)+' '+h(176,8),'%d.%m.%y %H.%M.%S')
    o=256; f=lambda w: [b[o+i*w+k*w: o+(i+1)*w+k*w] for i in range(ns)]
    def col(w,off):
        return [b[off+i*w:off+(i+1)*w].decode('latin1').strip() for i in range(ns)]
    labels=col(16,256); off=256+16*ns
    trans=col(80,off); off+=80*ns
    units=col(8,off); off+=8*ns
    pmin=[float(x) for x in col(8,off)]; off+=8*ns
    pmax=[float(x) for x in col(8,off)]; off+=8*ns
    dmin=[float(x) for x in col(8,off)]; off+=8*ns
    dmax=[float(x) for x in col(8,off)]; off+=8*ns
    off+=80*ns
    nsamp=[int(x) for x in col(8,off)]; off+=8*ns
    off+=32*ns
    assert off==int(h(184,8)), (off, h(184,8))
    recsize=sum(nsamp)*2
    recs=[]
    for r in range(nrec):
        base=off+r*recsize; p=base; rec={}
        for i in range(ns):
            vals=struct.unpack('<%dh'%nsamp[i], b[p:p+2*nsamp[i]]); p+=2*nsamp[i]
            g=(pmax[i]-pmin[i])/(dmax[i]-dmin[i]) if dmax[i]!=dmin[i] else 1
            rec[labels[i]]=[pmin[i]+(v-dmin[i])*g for v in vals] if nsamp[i]>1 else pmin[i]+(vals[0]-dmin[i])*g
        recs.append(rec)
    sig=[dict(label=labels[i],unit=units[i],pmin=pmin[i],pmax=pmax[i],dmin=dmin[i],dmax=dmax[i],n=nsamp[i]) for i in range(ns)]
    return start,dur,sig,recs
