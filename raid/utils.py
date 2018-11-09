import array


def build_parity(sds, iters, datasegments, myeccmap, paritysegments):
    psds_list = {seg_num: array.array('i') for seg_num in range(myeccmap.paritysegments)}

    for i in range(iters):
        parities = {seg_num: 0 for seg_num in range(myeccmap.paritysegments)}
        for DSegNum in range(datasegments):
            b = next(sds[DSegNum])

            Map = myeccmap.DataToParity[DSegNum]
            for PSegNum in Map:
                if PSegNum > paritysegments:
                    myeccmap.check()
                    raise Exception("eccmap error")

                parities[PSegNum] = parities[PSegNum] ^ b

        for PSegNum in range(myeccmap.paritysegments):
            psds_list[PSegNum].append(parities[PSegNum])

    for PSegNum in psds_list:
        psds_list[PSegNum].byteswap()

    return psds_list


def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]
