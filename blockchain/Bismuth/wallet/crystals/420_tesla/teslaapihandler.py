import time
import json
import hashlib
import datetime
import requests
import rainflow
import mypolyfit as mp
from requests_oauth2 import OAuth2BearerToken
import string
import random
import base64
from teslapy import Tesla

class TeslaAPIHandler():

    def __init__(self,bismuth,reg,unreg,op_data):
        self.address = "Bis1TeSLaWhTC2ByEwZnYWtsPVK5428uqnL46"
        self.bismuth = bismuth
        self.register = reg
        self.unregister = unreg
        self.op_data = op_data

    def fetch_vehicle_data(self,email,pwd):
        """
        Returns a dict with vehicle data for all VINs using Tesla API
        """
        try:
            data = self.tesla_data(email)
        except:
            print("Vehicle unavailable, trying again. ")
            data = self.tesla_data(email)

        N = data["count"]
        out = {}
        out["total"] = N
        out["vin"] = {}

        for i in range(0,N):
            vin = data["vehicle"][i]["vin"]
            if len(pwd)>0:
                vin = (vin + pwd).encode("utf-8")
                vin = hashlib.sha256(vin).hexdigest()
            checksum = self.checksum(vin,True)
            vin = vin + checksum
            out["vin"][str(i)] = vin
            out[vin] = {}
            out[vin]["battery_type"] = data["vehicle"][i]["battery_type"]
            out[vin]["battery_level"] = data["vehicle"][i]["battery_level"]
            out[vin]["battery_range"] = data["vehicle"][i]["battery_range"]
            out[vin]["usable_battery_level"] = data["vehicle"][i]["usable_battery_level"]
            out[vin]["charge_current_request"] = data["vehicle"][i]["charge_current_request"]
            out[vin]["charge_energy_added"] = data["vehicle"][i]["charge_energy_added"]
            out[vin]["charge_miles_added_ideal"] = data["vehicle"][i]["charge_miles_added_ideal"]
            out[vin]["charge_miles_added_rated"] = data["vehicle"][i]["charge_miles_added_rated"]
            out[vin]["ideal_battery_range"] = data["vehicle"][i]["ideal_battery_range"]
            out[vin]["est_battery_range"] = data["vehicle"][i]["est_battery_range"]
            out[vin]["outside_temp"] = json.dumps(data["vehicle"][i]["outside_temp"])
            out[vin]["inside_temp"] = json.dumps(data["vehicle"][i]["inside_temp"])
            out[vin]["odometer"] = data["vehicle"][i]["odometer"]
            out[vin]["timestamp"] = data["vehicle"][i]["timestamp"]
            out[vin]["car_version"] = data["vehicle"][i]["car_version"]
            out[vin]["car_type"] = data["vehicle"][i]["car_type"]
            out[vin]["exterior_color"] = data["vehicle"][i]["exterior_color"]
            out[vin]["wheel_type"] = data["vehicle"][i]["wheel_type"]

        return out

    def get_chain_data(self,asset_id,addresses,variable,filter,range_unit,temperature,startdate,enddate):
        """
        Returns vehicle data on chain as specified by 'variable' between start and end dates
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
        last_charge = 0
        sum_monthly = -1
        sum_distance = 0
        sum_charge = 0
        cycle_start = startdate
        cycle_end = enddate

        for sender in addresses.split(","):
            bisdata = self.bismuth.command(command, [sender,rec,op,1,False,t0,t1])
            for i in range(0,len(bisdata)):
                data = json.loads(bisdata[i][11])
                try:
                    vin = data["vin"]["0"]
                except:
                    vin = ''

                if len(vin) > 0:
                    if "monthly_" in variable:
                        if vin == asset_id:
                            ts = int(data[vin]["timestamp"])/1000
                            month = datetime.datetime.fromtimestamp(ts).strftime("%B %Y")
                            if month != last_month:
                                if sum_monthly != -1:
                                    out["x"].append(last_month)
                                    if "_efficiency" in variable:
                                        if sum_distance>0:
                                            out["y"].append(round(1e6*sum_charge/sum_distance)/1e3)
                                        else:
                                            out["y"].append("Not defined")
                                    elif "_cycles" in variable:
                                        cycle_end = datetime.datetime.fromtimestamp(ts-86400).strftime("%Y-%m-%d")
                                        cycle_data = self.get_cycle_data(asset_id,sender,"battery_level",0,range_unit,temperature,cycle_start,cycle_end)
                                        cycle_start = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                                        out["y"].append(cycle_data["full_cycle_equivalent"])
                                    else:
                                        out["y"].append(self.data_units(round(1000*sum_monthly)/1000,variable,range_unit,temperature))
                                else:
                                    last_distance = data[vin]["odometer"]
                                sum_distance = 0
                                sum_charge = 0
                                sum_monthly = 0

                            sum_distance += data[vin]["odometer"]-last_distance
                            if data[vin]["charge_energy_added"] != last_charge:
                                sum_charge += data[vin]["charge_energy_added"]

                            if "monthly_distance" in variable:
                                sum_monthly += data[vin]["odometer"] - last_distance
                            if "monthly_energy" in variable:
                                if data[vin]["charge_energy_added"] != last_charge:
                                    sum_monthly += data[vin]["charge_energy_added"]

                            last_distance = data[vin]["odometer"]
                            last_charge = data[vin]["charge_energy_added"]
                            last_month = datetime.datetime.fromtimestamp(ts).strftime("%B %Y")
                    else:
                        if variable == "max_range_vs_odometer":
                            data[vin]["max_range_vs_odometer"] = self.__get_max_range(data[vin])
                        if variable == "est_max_range":
                            data[vin]["est_max_range"] = self.__get_max_range(data[vin])
                        ts = int(data[vin]["timestamp"])/1000
                        mydate = datetime.datetime.fromtimestamp(ts)
                        try:
                            if vin == asset_id:
                                out["y"].append(self.data_units(data[vin][variable],variable,range_unit,temperature))
                                if "_vs_odometer" in variable:
                                    out["x"].append(data[vin]["odometer"])
                                else:
                                    out["x"].append(f"{mydate:%Y-%m-%d %H:%M:%S}")
                                out["z"] = 0
                        except:
                            pass

        if "monthly_" in variable:
            out["x"].append(datetime.datetime.fromtimestamp(ts).strftime("%B %Y"))
            if "_efficiency" in variable:
                if sum_distance>0:
                    out["y"].append(round(1e6*sum_charge/sum_distance)/1e3)
                else:
                    out["y"].append("Not defined")
            elif "_cycles" in variable:
                cycle_end = datetime.datetime.fromtimestamp(ts+86400).strftime("%Y-%m-%d")
                cycle_data = self.get_cycle_data(asset_id,sender,"battery_level",0,range_unit,temperature,cycle_start,cycle_end)
                out["y"].append(cycle_data["full_cycle_equivalent"])
            else:
                out["y"].append(self.data_units(round(1000*sum_monthly)/1000,variable,range_unit,temperature))

        if variable == "max_range_vs_odometer":
            out["z_x"] = []
            out["z_y"] = []
            if len(out["x"])>2:
                w = mp.polyfit(out["x"],out["y"],2,filter)
                data = mp.interpolate(min(out["x"]),max(out["x"]),20,w)
                out["z_x"] = data["x"]
                out["z_y"] = data["y"]

        return out

    def get_cycle_data(self,asset_id,addresses,variable,filter,range_unit,temperature,startdate,enddate):
        """
        Returns cycle data on chain as specified by 'variable' between start and end dates
        """
        out = {}
        out["x"] = []
        out["y"] = []
        out["full_cycle_equivalent"] = 0
        data = self.get_chain_data(asset_id,addresses,variable,filter,range_unit,temperature,startdate,enddate)
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

    def myparse(self,html,search_string):
        L = len(search_string)
        i = html.find(search_string)
        j = html.find('"',i+L+1)
        return html[i+L:j]

    def myparse2(self,html,search_string):
        L = len(search_string)
        i = html.find(search_string)
        j = html.find('&',i+L+1)
        return html[i+L:j]

    def html_parse(self,data,html):
        data['_csrf'] = self.myparse(html,'name="_csrf" value="')
        data['_phase'] = self.myparse(html,'name="_phase" value="')
        data['_process'] = self.myparse(html,'name="_process" value="')
        data['transaction_id'] = self.myparse(html,'name="transaction_id" value="')
        return data

    def __tesla_connect(self,email):
        """
        Connect to vehicles associated with email address
        """
        self.tesla = Tesla(email)
        self.tesla.fetch_token()

    def tesla_vins(self,email,pwd):
        """
        Returns all VIN numbers associated with specified email
        """
        self.__tesla_connect(email)
        vehicle = self.fetch_vehicle_data(email,pwd)
        out = {}
        L = vehicle["total"]
        out["vehicle"] = {}
        out["count"] = L
        for i in range(0,L):
            vin=vehicle['vin'][str(i)]
            out["vehicle"][str(i)] = vin

        return out

    def tesla_data(self,email):
        """
        Returns selected vehicle data given email.
        If owner has multiple vehicles, data for all of them is returned.
        """
        S = self.__tesla_connect(email)
        out = {}
        out["vehicle"] = {}
        out["count"] = 0

        selected = prod = self.tesla.vehicle_list()
        for i, product in enumerate(selected):
            product.sync_wake_up()
            out["count"] = out["count"] + 1
            data = product.get_vehicle_data()
            battery_type = ""
            try:
                option_codes = data["option_codes"].split(",")
                for j in range(len(option_codes)):
                    if option_codes[j].find("BT") == 0:
                        battery_type = option_codes[j]
                        break
            except:
                pass

            vin=data["vin"]
            out["vehicle"][i] = {}
            out["vehicle"][i]["charge_energy_added"] = data["charge_state"]["charge_energy_added"]
            out["vehicle"][i]["charge_miles_added_rated"] = data["charge_state"]["charge_miles_added_rated"]
            out["vehicle"][i]["charge_miles_added_ideal"] = data["charge_state"]["charge_miles_added_ideal"]
            out["vehicle"][i]["est_battery_range"] = data["charge_state"]["est_battery_range"]
            out["vehicle"][i]["ideal_battery_range"] = data["charge_state"]["ideal_battery_range"]
            out["vehicle"][i]["charge_current_request"] = data["charge_state"]["charge_current_request"]
            out["vehicle"][i]["usable_battery_level"] = data["charge_state"]["usable_battery_level"]
            out["vehicle"][i]["battery_range"] = data["charge_state"]["battery_range"]
            out["vehicle"][i]["battery_level"] = data["charge_state"]["battery_level"]
            out["vehicle"][i]["timestamp"] = data["charge_state"]["timestamp"]
            out["vehicle"][i]["odometer"] = data["vehicle_state"]["odometer"]
            out["vehicle"][i]["inside_temp"] = data["climate_state"]["inside_temp"]
            out["vehicle"][i]["outside_temp"] = data["climate_state"]["outside_temp"]
            out["vehicle"][i]["car_version"] = data["vehicle_state"]["car_version"]
            out["vehicle"][i]["battery_type"] = battery_type
            out["vehicle"][i]["car_type"] = data["vehicle_config"]["car_type"]
            out["vehicle"][i]["exterior_color"] = data["vehicle_config"]["exterior_color"]
            out["vehicle"][i]["wheel_type"] = data["vehicle_config"]["wheel_type"]
            out["vehicle"][i]["vin"] = vin

        return out

    def __decode_char(self,c):
        """
        Transliteration keys, see https://en.wikipedia.org/wiki/Vehicle_identification_number
        """
        options = {'1':1,'2':2,'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,
                   'A':1,'B':2,'C':3,'D':4,'E':5,'F':6,'G':7,'H':8,
                   'J':1,'K':2,'L':3,'M':4,'N':5,      'P':7,      'R':9,
                         'S':2,'T':3,'U':4,'V':5,'W':6,'X':7,'Y':8,'Z':9}
        try:
           w = 0
           w = options[c]
        except:
            pass
        return w

    def __weight(self,pos):
        """
        Weight factors, see https://en.wikipedia.org/wiki/Vehicle_identification_number
        """
        options= {0:8,1:7,2:6,3:5,4:4,5:3,6:2,7:10,8:0,9:9,10:8,11:7,12:6,13:5,14:4,15:3,16:2,17:6}
        try:
            w = 0
            w = options[pos]
        except:
            pass
        return w

    def checkVIN(self,vin):
        """
        Returns out=1 if specified VIN is valid, out=-1 otherwise.
        """
        out=-1
        try:
            sum = 0
            N = len(vin)
            if N>10:
                check_in=vin[8]
                for i in range(0,N):
                    sum += self.__weight(i)*self.__decode_char(vin[i]);
                compare = sum % 11
                if (compare == 11):
                    check = 'X'
                else:
                    check = str(compare)

                if (check_in == check):
                   out = 1
        except:
            pass

        return out;

    def checkID(self,asset_id):
        """
        Returns out=1 if specified asset ID is valid, out=-1 otherwise.
        """
        out=-1
        crc=self.checksum(asset_id,False)
        if asset_id.endswith(crc):
            out=1
        return out;

    def data_units(self,data,var,range_unit,temperature):
        """
        Returns either range or temperature with the specified unit.
        Range or temperature is chosen based on keyword in the string var.
        It is assumed that the input data is by default in either miles or Celsius.
        """
        out = data
        if temperature == "F":
            if var.find("temp") > 0:
                out = round(data*1.8 + 32.0,1)

        if range_unit == "km":
            if (var.find("miles") > 0) or (var.find("range") > 0) or \
                (var.find("meter") > 0) or (var.find("distance") > 0):
                out = round(data*1.609344,3)

        return out

    def __get_max_range(self,data):
        range = 0
        if data["battery_level"]>0:
            range = data["battery_range"] / (data["battery_level"]/100.0)
        range = round(range,3)
        return range

    def __normalize(self,out):
        y = out["y"]
        M = max(y)
        out["y"] = [x/M for x in y]
        return out

    def encryptDecrypt(self,input,key):
        N = len(key)
        if N>0:
            out = ""
            M = len(input)
            j = 0
            for i in range(M):
                out = out[:i] + chr(ord(input[i]) ^ ord(key[j]))
                j = j + 1
                if j == N:
                    j = 0
        else:
            out=input
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

    def full_cycle_equivalent(self,cycle):
        factor = { 10: 0.043, 20: 0.086, 30: 0.155, 40: 0.225, 50: 0.400, 60: 0.500, 70: 0.600, 80: 0.700, 90: 0.850, 100: 1.0 }
        return round(100 * factor[cycle[0]] * cycle[1])/100.0
