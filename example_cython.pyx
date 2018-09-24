import struct
import cython
import itertools

unpack = struct.Struct('>l').unpack
pack = struct.Struct('>l').pack


def build_parity(sds, iters, datasegments, INTSIZE, myeccmap, paritysegments, parities):
    cdef int i
    cdef int DSegNum
    cdef int PSegNum
    cdef dict psds_list = {seg_num: [] for seg_num in xrange(myeccmap.paritysegments)}

    for i in xrange(iters):
        for DSegNum in xrange(datasegments):
            bstr = next(sds[DSegNum])

            assert len(bstr) == INTSIZE, 'strange read under INTSIZE bytes, len(bstr)=%d DSegNum=%d' % (len(bstr), DSegNum)

            b, = unpack(bstr)
            Map = myeccmap.DataToParity[DSegNum]
            for PSegNum in Map:
                if PSegNum > paritysegments:
                    myeccmap.check()
                    raise Exception("eccmap error")

                parities[PSegNum] = parities[PSegNum] ^ b

        for PSegNum in xrange(myeccmap.paritysegments):
            bstr = pack(parities[PSegNum])
            psds_list[PSegNum].append(bstr)

    for PSegNum in psds_list:
        psds_list[PSegNum] = ''.join(psds_list[PSegNum])

    return psds_list


def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    cdef int i
    for i in xrange(0, len(l), n):
        yield l[i:i + n]
