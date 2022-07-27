import numpy as np
import time
import struct
import serial
import threading
from ctypes import *
import ctypes

lib=ctypes.CDLL(r"./encoding_LK.dll") 

T_LIMIT=100

P_MIN =0
P_MAX =355.99
V_MIN =-30
V_MAX =30
POSITION_ORDER= b"\x02\x02\x0B\x04\x9C\x7E\x03"


# Python representation of the C struct re_val
class ReVal(Structure):
    _fields_ = [("L1", c_uint64),("L2", c_uint32),("L3", c_uint16)]

class motor():

    def __init__(self, motor_id, com1='com11',com2='com9', bps1=115200,bps2=115200):
        self.id=motor_id

        self.disable = -4
        self.enable = -3
        self.setzero= -2

        # 设置串口通讯 

        self.serial_uart = serial.Serial(com1, bps1)
        self.serial_uart.timeout = 0
        self.serial_uart.bytesize = 8
        self.serial_uart.stopbits = 1
        self.serial_uart.parity = "N"

        '''
        self.serial_can = serial.Serial(com2, bps2)
        self.serial_can.timeout = 0
        self.serial_can.bytesize = 8
        self.serial_can.stopbits = 1
        self.serial_can.parity = "N"
        '''

        self.data=[]
        self.crc=[]

    def motor_enable(self):
        try:
            self.serial_uart.write(struct.pack(">ii", -4,self.enable))
        except:
            print('cant write motor_enable')

    def motor_disable(self):
            self.serial_uart.write(struct.pack(">ii", -4,self.disable))
    '''
    def motor_setzero(self):
        try:
            #self.serial_can.write(struct.pack(">ii", -4,self.setzero))
            self.serial_uart.write(SETZERO_UART)
        except:
            print('cant write motor_setzero')
    '''


    def motor_sent(self,mode,MotorPara):
        #多线程
        threads = []
        t1 = threading.Thread(target=self.motor_read)
        threads.append(t1)

        if mode=='P' :
            t2 = threading.Thread(target=self.motor_Pctrl_can,args=(MotorPara))
        elif  mode=='V' :
            t2 = threading.Thread(target=self.motor_sent)
        elif mode=='T':
            t2 = threading.Thread(target=self.motor_sent)
        else:
            print("motor_sent wrong")

        threads.append(t2)
        for t in threads:
            t.start()

    def motor_Pctrl(self, MotorPara):
        ID=MotorPara[0,:,0]
        Pdes=MotorPara[1,:,0]
        Ddes = MotorPara[2, :, 0]

        #limit data to be within bounds
        sent=[]

        for i in range(T_LIMIT):
            Pdes[i]=np.min([ np.max([Pdes[i],P_MIN]),P_MAX])
            Pdes[i]=Pdes[i]*100

            lib.packmsg.restype=ReVal
            pacmsg=lib.packmsg ( c_char(b'p'),c_ubyte(int(ID[i])),c_ubyte(int(Ddes[i])),c_ushort(int(Pdes[i])) )

            report=pacmsg.L1.to_bytes(8,byteorder="big")+pacmsg.L3.to_bytes(2,byteorder="big")
            #report=struct.pack(">QH",pacmsg.L1,pacmsg.L3)

            #report=b"\x3E\xA3\x01\x08\xEA\x00\x00\x00\x00\x00\x00\x00\x00\x00 "
            print(report.hex(),len(report))
            
            
            self.serial_uart.write(report)
            time.sleep(0.1)


    def motor_Pctrl_can(self,MotorPara):
        # pdes=np.linspace(0,95.5,100)
        ID=MotorPara[0,:,0]
        Pdes=MotorPara[1,:,0]
        Vdes = MotorPara[2, :, 0]
        tff = MotorPara[3, :, 0]
        kd = MotorPara[4, :, 0]
        kp = MotorPara[5, :, 0]

        #limit data to be within bounds
        sent=[]
        for i in range(T_LIMIT):
            Pdes[i]=np.min([ np.max([Pdes[i],P_MIN]),P_MAX])
            Vdes[i] = np.min([ np.max([Vdes[i], V_MIN]), V_MAX])


            report=(int(Pdes[i])<<48)+(int(Vdes[i])<<36)+(int(kp[i])<<24)+(int(kd[i])<<12)+int(tff[i])
            sent.append(report)
            rbi=struct.pack(">Q", report)

            self.serial_can.write(rbi)

            time.sleep(0.1)

    def  float_to_uint(self, x,  x_min,  x_max, bits):
        span = x_max - x_min
        if(x < x_min):
            x = x_min
        elif(x > x_max) :
            x = x_max
        p=int( (x- x_min)*float((1<<bits)-1)/span  )
        #print(p)
        return p
    def uint_to_float(x_int, x_min,x_max,bits):
        span = x_max - x_min
        return  float(x_int)*span/float((1<<bits)-1) + x_min

    def motor_read(self):
        while True:
            n = self.serial_uart.inWaiting()  # 等待数据的到来，并得到数据的长度
            if n:  # 如果有数�??
                begin = self.serial_uart.read(1)  # 读取n位数�??
                if begin=='02':
                    datalen = self.serial_uart.read(1)
                    data=self.serial_uart.read(int(datalen))
                    CRC16=self.serial_uart.read(2)
                    end=self.serial_uart.read(1)
                    if end=='03':
                        self.data.append(data)
                        self.crc.append(CRC16)
                    else: print('read data error')

                """
                s = [hex(x) for x in bytes(n)]
                id=(int(s[0],16)<<4)+(int(s[1],16))
                p=(int(s[2],16)<<4)+(int(s[3],16))
                v=(int(s[4],16)<<12)+(int(s[5],16)<<8)+(int(s[6],16)<<4)+(int(s[7],16))
                t=(int(s[8],16)<<8)+(int(s[9],16)<<4)+(int(s[10],16))

                p=self.uint_to_float(p,P_MIN,P_MAX,16)
                v = self.uint_to_float(v, V_MIN, V_MAX, 12)
                t = self.uint_to_float(t, T_MIN, T_MAX, 12)

                print("P:",p,"\nV:",v,"\nT:",t)
                """
            time.sleep(0.5)


if __name__ == '__main__':
    Motorlist=[1]
    MyMotor=[]
    MyMotor.append(motor(Motorlist[0]))

    ID=np.ones(T_LIMIT)*Motorlist[0]
    Pdes = np.linspace(0, 300, T_LIMIT)
    Ddes=np.ones(100)*0


    MotorPara =np.array([ID,Pdes,Ddes]) #ID CMD VALUE
    MotorPara=np.expand_dims(MotorPara, axis=2) #n个电机

    MyMotor[0].motor_Pctrl(MotorPara)

    print(MyMotor[0].data,'\n',MyMotor[0].crc)






