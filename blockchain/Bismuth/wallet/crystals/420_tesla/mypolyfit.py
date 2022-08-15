# Makes polyfit and interpolate available without having to install the entire numpy lib
# Date: 2020-04-26, GH2
#

def polyfit(x,y,degree,filter):
    w = []
    M = float(filter)*max(y)
    N = len(y)
    Y = [[y[row] for col in range(1)] for row in range(N) if y[row]>M]
    NY = len(Y)
    if NY>=degree:
        A = [[x[row]**(degree-1-col) for col in range(degree)] for row in range(N) if y[row]>M]
        AT = matrix_transpose(A)
        ATA = matrix_mult(AT,A)
        b = matrix_mult(AT,Y)
        w = gauss(ATA,b) #Weights found by pseudo-inverse of A*w = Y
    return w

def interpolate(xmin,xmax,N,w):
    out = {}
    out["x"] = []
    out["y"] = []
    try:
        Nw = len(w)
        if (xmax>xmin) and (N>1) and (Nw>1):
            stepsize = (xmax - xmin) / (N-1)
            for i in range(N):
                x = xmin + i*stepsize
                out["x"].append(x)
                temp = 0
                for j in range(Nw):
                    temp += (x**(Nw-1-j))*w[j]
                out["y"].append(temp)
    except:
        pass
    return out

def matrix_transpose(A):
    N = len(A)
    M = len(A[0])
    AT = [[A[col][row] for col in range(N)] for row in range(M)]
    return AT

def matrix_mult(X,Y):
    result = [[sum(a*b for a,b in zip(X_row,Y_col)) for Y_col in zip(*Y)] for X_row in X]
    return result

def gauss(ATA,b):
    # Assemble A from ATA and b
    n = len(ATA)
    A = [[0 for col in range(n+1)] for row in range(n)]
    for i in range(0,n):
        for j in range(0,n):
            A[i][j] = ATA[i][j]
        A[i][n] = b[i][0]

    # From here: https://martin-thoma.com/solving-linear-equations-with-gaussian-elimination
    n = len(A)
    for i in range(0, n):
        maxEl = abs(A[i][i])
        maxRow = i
        for k in range(i + 1, n):
            if abs(A[k][i]) > maxEl:
                maxEl = abs(A[k][i])
                maxRow = k
        for k in range(i, n + 1):
            tmp = A[maxRow][k]
            A[maxRow][k] = A[i][k]
            A[i][k] = tmp
        for k in range(i + 1, n):
            c = -A[k][i] / A[i][i]
            for j in range(i, n + 1):
                if i == j:
                    A[k][j] = 0
                else:
                    A[k][j] += c * A[i][j]
    x = [0 for i in range(n)]
    for i in range(n - 1, -1, -1):
        x[i] = A[i][n] / A[i][i]
        for k in range(i - 1, -1, -1):
            A[k][n] -= A[k][i] * x[i]
    return x
