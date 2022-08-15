import re
import time
import json
import hashlib
import datetime
import requests
import rainflow
from subprocess import Popen, PIPE

class PhoneAPIHandler():

    def __init__(self,bismuth,reg,unreg,op_data):
        self.bismuth = bismuth
        self.address = "Bis1QPHone8oYrrDRjAFW1sNjyJjUqHgZhgAw"
        self.register = reg
        self.unregister = unreg
        self.op_data = op_data

    def fetch_asset_data(self,pwd):
        """
        Returns a dict with asset data
        """
        data = self.asset_data(pwd)
        N = data["count"]
        out = {}
        out["total"] = N
        out["asset_id"] = {}

        try:
            for i in range(0,N):
                I = str(i)
                asset_id = data["phone"][I]
                out["asset_id"][str(i)] = asset_id
                out[asset_id] = {}
                out[asset_id] = data["phone"][asset_id]
        except:
            out["total"] = 0

        return out

    def get_chain_data(self,addresses,id,variable,temperature,startdate,enddate):
        """
        Returns asset data on chain as specified by 'variable' between start and end dates
        """
        out = {}
        out["x"] = []
        out["y"] = []
        out["z"] = []
        command = "addlistopfromto"
        rec = self.address
        op = self.op_data
        t0 = time.mktime(datetime.datetime.strptime(startdate, "%Y-%m-%d").timetuple())
        t1 = time.mktime(datetime.datetime.strptime(enddate, "%Y-%m-%d").timetuple())
        t1 = t1 + 24*60*60 #Enddate Time 23:59:59
        last_month = ""
        cycle_start = startdate
        cycle_end = enddate
        sum_monthly = -1

        for sender in addresses.split(","):
            bisdata = self.bismuth.command(command, [sender,rec,op,1,False,t0,t1])
            for i in range(0,len(bisdata)):
                data = json.loads(bisdata[i][11])
                asset_id = self.sanitize(data["asset_id"]["0"])
                if "monthly_" in variable:
                    if id == asset_id:
                        ts = int(data[id]["timestamp"])/1000
                        month = datetime.datetime.fromtimestamp(ts).strftime("%B %Y")
                        if month != last_month:
                            if sum_monthly != -1:
                                out["x"].append(last_month)
                                if "_cycles" in variable:
                                    cycle_end = datetime.datetime.fromtimestamp(ts-86400).strftime("%Y-%m-%d")
                                    cycle_data = self.get_cycle_data(sender,asset_id,"percentage",temperature,cycle_start,cycle_end)
                                    cycle_start = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                                    out["y"].append(cycle_data["full_cycle_equivalent"])
                            sum_monthly = 0
                        last_month = datetime.datetime.fromtimestamp(ts).strftime("%B %Y")
                else:
                    if (asset_id == id) and (self.checkID(asset_id)==1):
                        ts = int(data[asset_id]["timestamp"])/1000
                        mydate = datetime.datetime.fromtimestamp(ts)
                        try:
                            if id == asset_id:
                                out["y"].append(self.data_units(data[asset_id][variable],variable,temperature))
                                out["x"].append(f"{mydate:%Y-%m-%d %H:%M:%S}")
                                out["z"] = 0
                        except:
                            pass

        if "monthly_" in variable:
            out["x"].append(datetime.datetime.fromtimestamp(ts).strftime("%B %Y"))
            if "_cycles" in variable:
                cycle_end = datetime.datetime.fromtimestamp(ts+86400).strftime("%Y-%m-%d")
                cycle_data = self.get_cycle_data(sender,asset_id,"percentage",temperature,cycle_start,cycle_end)
                out["y"].append(cycle_data["full_cycle_equivalent"])

        return out

    def get_cycle_data(self,addresses,id,variable,temperature,startdate,enddate):
        """
        Returns cycle data on chain as specified by 'variable' between start and end dates
        """
        out = {}
        out["x"] = []
        out["y"] = []
        out["full_cycle_equivalent"] = 0
        data = self.get_chain_data(addresses,id,variable,temperature,startdate,enddate)
        try:
            cycles = rainflow.count_cycles(data["y"], binsize=10.0)
            sum = 0.0
            for i in range(len(cycles)):
                out["x"].append("Cycle {}-{}%".format(cycles[i][0]-10,cycles[i][0]))
                out["y"].append(cycles[i][1])
                sum += self.full_cycle_equivalent(cycles[i])
            out["full_cycle_equivalent"] = round(100*sum)/100
        except:
            pass
        return out

    def asset_id(self,pwd):
        """
        Returns phone's asset ID
        """
        out = {}
        out["count"] = 0
        try:
            process = Popen(['termux-telephony-deviceinfo'], stdout=PIPE, stderr=PIPE)
            stdout, stderr = process.communicate()
            data = json.loads(stdout)

            out["phone"] = {}
            if len(pwd) == 0:
                asset_id = data["device_id"]
                checksum = self.checksum(asset_id,True)
            else:
                asset_id = (data["device_id"] + pwd).encode("utf-8")
                asset_id = hashlib.sha256(asset_id).hexdigest()
                checksum = self.checksum(asset_id,True)

            out["phone"]["0"] = asset_id + checksum
            out["count"] = 1
        except:
            pass
        return out

    def asset_data(self,pwd):
        """
        Returns phone battery data
        """
        out = {}
        out["count"] = 0

        try:
            out = self.asset_id(pwd)
            process = Popen(['termux-battery-status'], stdout=PIPE, stderr=PIPE)
            stdout, stderr = process.communicate()
            data = json.loads(stdout)

            asset_id = out["phone"]["0"]
            data["timestamp"] = round(1000*time.time())
            out["phone"][asset_id] = data
        except:
            pass
        return out

    def checkID(self,asset_id):
        """
        Returns out=1 if specified asset ID is valid, out=-1 otherwise.
        """
        out=-1
        crc=self.checksum(asset_id,False)
        if asset_id.endswith(crc):
            out=1
        return out;

    def data_units(self,data,var,temperature):
        """
        Returns either range or temperature with the specified unit.
        Range or temperature is chosen based on keyword in the string var.
        It is assumed that the input data is by default in either miles or Celsius.
        """
        out = data
        if var == "current":
            out = round(out/1000.0,3)
        elif temperature == "F":
            if var.find("temp") >= 0:
                out = round(data*1.8 + 32.0,1)
        return out

    def checksum(self,input,lastchar : bool = True):
        if lastchar == True:
            M = len(input)
        else:
            M = len(input) - 1
        out = 0
        for i in range(M):
            out = out + ord(input[i])
        return format(out % 16,"x")

    def sanitize(self,input):
        out = re.sub('[\W_]', '', input)
        return out

    def full_cycle_equivalent(self,cycle):
        factor = { 10: 0.043, 20: 0.086, 30: 0.155, 40: 0.225, 50: 0.400, 60: 0.500, 70: 0.600, 80: 0.700, 90: 0.850, 100: 1.0 }
        return round(100 * factor[cycle[0]] * cycle[1])/100.0
