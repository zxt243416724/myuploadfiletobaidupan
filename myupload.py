# !/usr/bin/env python3
"""
    xpan upload
    include:
        precreate
        upload
        create
"""
import os
import sys
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
from pprint import pprint
from openapi_client.api import fileupload_api
import openapi_client
import hashlib


class SingleFile():
    def __init__(self,file_path:str) -> None:
        #本地的文件名
        self.local_path=file_path
        #本地文件的路径

        #待上传的文件的长度
        self.file_length=0
        #待上传的文件的md5列表
        self.block_md5list=[]

        self.block_md5list,self.file_length=self.calculate_md5(file_path)
        #文件名
        self.file_name=os.path.basename(file_path)

        #上传ID(从服务器获取到的)
        self.uploadid=""  
        #上传后在服务器上的路径绝对路径
        self.upload_server_path=""
     
        #当前待上传的分块的编号
        self.to_upload_block_no=int(0)
        #当前上传的块的临时文件路径
        self.to_upload_block_temp_file_path=""

        #': 'P1-MTAuMTQ2Ljc0LjM3OjE3MDE0ODQyOTc6ODkzMjY5MDQ3MTQwODk5MjIwMg=='}
        #块大小固定长度
        self.block_size=4 * 1024 * 1024

        self.str_block_list=""
    def update_context_path(self,local_context_path,server_context_path):
        """
        计算这个文件上传后在服务端的路径，获取他们的路径公共部分
        """
        cl=len(local_context_path)
        common_path= self.local_path[cl:]
        self.upload_server_path=server_context_path+"/"+common_path
        
        #os.path.join(server_context_path,common_path)
        print("upload_server_path={}".format(self.upload_server_path))

     
    def calculate_md5(self,file_path:str, block_size=4 * 1024 * 1024):
        """
        计算文件的分块 MD5 值。
        :param file_path: 文件的路径。
        :param block_size: 每个块的大小（以字节为单位），默认为4MB。
        :return: 每个块的 MD5 值组成的列表。
        """
        md5_list = []
        file_length = 0

        with open(file_path, 'rb') as file:
            while True:
                # 读取文件的一块内容
                data = file.read(block_size)
                if not data:
                    break
                # 累加文件长度
                file_length += len(data)

                # 计算这个块的 MD5 值，并添加到列表中
                md5_hash = hashlib.md5(data).hexdigest()
                md5_list.append(md5_hash)

        return md5_list,file_length

    def copy_data_to_new_file(self,source_file_path, target_file_path, offset, length):
        """
        从源文件的指定偏移处读取一定长度的数据，并写入到目标文件。
        :param source_file_path: 源文件的路径。
        :param target_file_path: 目标文件的路径。
        :param offset: 要开始读取的偏移量（以字节为单位）。
        :param length: 要读取的数据长度（以字节为单位）。
        """
        with open(source_file_path, 'rb') as source_file:
            # 移动到指定的偏移量
            source_file.seek(offset)
            # 从偏移量处读取指定长度的数据
            data = source_file.read(length)

        with open(target_file_path, 'wb') as target_file:
            # 将读取的数据写入到目标文件
            target_file.write(data)

    def get_cur_block_file(self):
        """
        获取当前待上传的分块文件
        """
        if  len(self.block_md5list)<=1:
            #只有一个分块,那就是这个文件
            return self.local_path
        else:
            if  self.to_upload_block_no>=len(self.block_md5list):
              #已经上传完
              return ""
            
            offset=self.to_upload_block_no*self.block_size
            #length
            have_upload_len=self.block_size*self.to_upload_block_no
            max_block_len=self.block_size
            if have_upload_len+max_block_len>self.file_length:
                have_upload_len=self.file_length-have_upload_len
            
            target_file_path=self.local_path+"_"
            target_file_path+=str(self.to_upload_block_no)
            
            #拷贝文件的一个小块
            if os.path.isfile(self.to_upload_block_temp_file_path):
                #当前的临时文件存在就删除
                if os.path.exists(self.to_upload_block_temp_file_path):
                    os.remove(self.to_upload_block_temp_file_path)

            self.to_upload_block_temp_file_path=target_file_path
            self.copy_data_to_new_file(self.local_path,target_file_path,offset,max_block_len)
       
            return target_file_path

    def get_to_upload_block_no(self):
        """
        获取当前待上传的分块编号
        """
        return self.to_upload_block_no

    def upload_curblock_success(self):
        """
        当前块上传成功
        """
        if os.path.isfile(self.to_upload_block_temp_file_path):
            #当前的临时文件存在就删除
            if os.path.exists(self.to_upload_block_temp_file_path):
                os.remove(self.to_upload_block_temp_file_path)
        self.to_upload_block_temp_file_path=""
        self.to_upload_block_no+=1
        num=len(self.block_md5list)
        progess=self.to_upload_block_no/(num*1.0)
        print("upload_curblock_success={}/{} progress={}".format( self.to_upload_block_no, num,progess))

    def have_next_to_upload_block(self):
        """
        是否有下个待上传的块
        """
        if self.to_upload_block_no>=len(self.block_md5list):
            return False
        return True

    def get_upload_server_path(self):
        """
        获取上传文件后在服务端的路径
        """
        return self.upload_server_path

    def get_blocks_num(self):
        return len(self.block_md5list)

class UploadTask():
    """
    一个上传文件的任务
    """
    def __init__(self,appname:str,in_server_context_path,access_token:str,file_path:str) -> None:
        """
        参数：
        appname: 百度控制台开的APP的名字 myuploadfile
        server_context_path:上传到服务端上的相对于  /apps/myuploadfile 的路径
        access_token: token
        file_path: 需要上传的文件路径

         path="/apps/"
            path+=self.appname

        """

        self.appname=appname
        self.access_token=access_token
        #待上传的文件列表
        self.toupload_fileslist=[]
        self.server_context_path="/apps/"
        self.server_context_path+=appname

        if in_server_context_path=="" or in_server_context_path=="./"  or  in_server_context_path==".\\":
            pass
        else:
            if os.path.isabs(in_server_context_path):
                #不能是个绝对路径
                raise Exception("server_context_path={} is isabs".format(in_server_context_path))
            else:
                self.server_context_path=os.path.join(self.server_context_path,in_server_context_path)

        cwd=os.getcwd()
        if os.path.isabs(file_path):
           #是个绝对路径
           self.client_context_path=os.path.dirname(file_path)  
        else:
           #是相对路径,转为绝对路径
           cpath=os.path.join(cwd,file_path)
           file_path=cpath
           self.client_context_path=cwd
        

        if os.path.isfile(file_path):
            sf=SingleFile(file_path)
            sf.update_context_path(self.client_context_path,self.server_context_path)
            self.toupload_fileslist.append(sf)
        else:
            #是目录
            pass

    def get_file_path_on_server(self,file_path):
        """
        获取待上传的文件在服务端的上的路径
        """
        if os.path.isabs(file_path):
            #是绝对路径
            pass

    def begin_upload(self):
        """
        开始上传
        """
        for sf in self.toupload_fileslist:
            if not self.upload_file(sf):
                return
        

    def upload_file(self,sf:SingleFile):
        self.precreate(sf)
        print("1------------------------------------------------->")
        self.upload(sf)
        print("2------------------------------------------------->")
        self.create(sf)
        print("3------------------------------------------------->")

    def precreate(self,sf:SingleFile):
        """
        precreate
        预上传一个文件

        返回信息
        {
            'block_list': [0, 1, 2, 3, 4, 5],
            'errno': 0,
            'request_id': 8932651341318900633,
            'return_type': 1,
            'uploadid': 'P1-MTAuNDAuMTI4Ljg3OjE3MDE0ODQxNTI6ODkzMjY1MTM0MTMxODkwMDYzMw=='
        }

        """
        #    Enter a context with an instance of the API client
        with openapi_client.ApiClient() as api_client:
            # Create an instance of the API class
            api_instance = fileupload_api.FileuploadApi(api_client)
            #access_token = "123.56c5d1f8eedf1f9404c547282c5dbcf4.YmmjpAlsjUFbPly3mJizVYqdfGDLsBaY5pyg3qL.a9IIIQ"  # str |
            #access_token = "a9f9183f8ae2ca27ad6bdaa03aa925f9"  # str |
            access_token=self.access_token
            
            #path = "/apps/myuploadfile/a.txt"  # str | 对于一般的第三方软件应用，路径以 "/apps/your-app-name/" 开头。对于小度等硬件应用，路径一般 "/来自：小度设备/" 开头。对于定制化配置的硬件应用，根据配置情况进行填写。
            """
            path="/apps/"
            path+=self.appname
            path+="/"
            path+=sf.file_name
            """
            path=sf.upload_server_path

            isdir = 0  # int | isdir
            #size = 271  # int | size
            size=sf.file_length
            autoinit = 1  # int | autoinit
            #block_list = '["d05f84cf5340d1ef0c5f6d6eb8ce13b8"]' # str | 由MD5字符串组成的list
            #block_list =sf.block_md5list
            str_block_list="["
            for index,blockmd5 in enumerate(sf.block_md5list):
                if index>0:
                    str_block_list+=",\""
                    str_block_list+=blockmd5
                    str_block_list+="\""
                else:
                    str_block_list+="\""
                    str_block_list+=blockmd5
                    str_block_list+="\""
            str_block_list+="]"
            print(str_block_list)
            block_list=str_block_list
            sf.str_block_list=block_list



            rtype = 3  # int | rtype (optional)

            # example passing only required values which don't have defaults set
            # and optional values
            try:
                api_response = api_instance.xpanfileprecreate(
                    access_token, path, isdir, size, autoinit, block_list, rtype=rtype)
                
                pprint(api_response)
                print(type(api_response))

                icode=int(api_response["errno"])
                if icode!=0:
                    print("failed precreate code={}".format(icode))
                    return False

                sf.uploadid=api_response["uploadid"]
                
                return True
            except openapi_client.ApiException as e:
                print("Exception when calling FileuploadApi->xpanfileprecreate: %s\n" % e)
                return False
        return False

   
    def upload(self,sf:SingleFile):
        """
        上传一个文件
        """
        # Enter a context with an instance of the API client
        with openapi_client.ApiClient() as api_client:
            # Create an instance of the API class
            api_instance = fileupload_api.FileuploadApi(api_client)
            #access_token = "123.56c5d1f8eedf1f9404c547282c5dbcf4.YmmjpAlsjUFbPly3mJizVYqdfGDLsBaY5pyg3qL.a9IIIQ"  # str |

            access_token=self.access_token
            #上传的分块的序号
         
            #path = "/apps/hhhkoo/a.txt"  # str |
            path=sf.get_upload_server_path()
            #uploadid = "N1-MTA2LjEzLjc2LjI0MDoxNjU0NTAwMDE0OjE3NDEzNzMyMTUxNTY1MTA2MQ=="  # str |
            uploadid=sf.uploadid
            #固定值 tmpfile
            type = "tmpfile"  # str |
            
            num_blocks=sf.get_blocks_num()
            while sf.have_next_to_upload_block():
                block_file_path=sf.get_cur_block_file()
                ipartseq=sf.get_to_upload_block_no()
                partseq =str(ipartseq)
                try:
                    file = open(block_file_path, 'rb') # file_type | 要进行传送的本地文件分片
                except Exception as e:
                    print("Exception when open file: %s\n" % e)
                    exit(-1)

                # example passing only required values which don't have defaults set
                # and optional values
                try:
                    api_response = api_instance.pcssuperfile2(
                        access_token, partseq, path, uploadid, type, file=file)
                    #pprint(api_response)
                    #设置上传当前分块成功
                    sf.upload_curblock_success()

                except openapi_client.ApiException as e:
                    print("Exception when calling FileuploadApi->pcssuperfile2: %s\n" % e)


    def create(self,sf:SingleFile):
        """
        create
        """
        # Enter a context with an instance of the API client
        with openapi_client.ApiClient() as api_client:
            # Create an instance of the API class
            api_instance = fileupload_api.FileuploadApi(api_client)
            #access_token = "123.56c5d1f8eedf1f9404c547282c5dbcf4.YmmjpAlsjUFbPly3mJizVYqdfGDLsBaY5pyg3qL.a9IIIQ"  # str |
            access_token=self.access_token
            #path = "/apps/hhhkoo/a.txt"  # str | 与precreate的path值保持一致
            path=sf.upload_server_path
            print("upload_server_path={}".format(sf.upload_server_path))

            isdir = 0  # int | isdir
            #size = 271 # int | 与precreate的size值保持一致
            size=sf.file_length
            #uploadid = "N1-MTA2LjEzLjc2LjI0MDoxNjU0NTAwMDE0OjE3NDEzNzMyMTUxNTY1MTA2MQ=="  # str | precreate返回的uploadid
            uploadid=sf.uploadid
            #block_list = '["d05f84cf5340d1ef0c5f6d6eb8ce13b8"]'  # str | 与precreate的block_list值保持一致
            block_list=sf.str_block_list

            rtype = 3  # int | rtype (optional)

            # example passing only required values which don't have defaults set
            # and optional values
            try:
                api_response = api_instance.xpanfilecreate(
                    access_token, path, isdir, size, uploadid, block_list, rtype=rtype)
                pprint(api_response)
            except openapi_client.ApiException as e:
                print("Exception when calling FileuploadApi->xpanfilecreate: %s\n" % e)


    def upload_local_file(file_path:str):
        """
        上传本地的文件,
        打开一个文件，读取大小，按4MB一个块，求MD5 值，帮我返回一个列表，这个列表每个元素就是每个块的MD5 值，不足4M 的也是一个块，也要求他的MD5 值
        """
        sf=SingleFile(file_path)
        return sf

import argparse

if __name__ == '__main__':
    print("http://openapi.baidu.com/oauth/2.0/authorize?response_type=code&client_id=Khw4t43kgD7T7thnKPQvCEm5bljme4LF&redirect_uri=oob&scope=basic,netdisk&device_id=44023534")
    parser = argparse.ArgumentParser(description="upload file to baiduwangpan")

    # 添加参数
    parser.add_argument('--file', '-f', type=str, required=False, default="K:\\cudnn-windows-x86_64-8.9.4.25_cuda11-archive.zip", help='Input file path')
    parser.add_argument('--token', '-t', type=str, required=False, default="121.abd37181019a036999e1614caedddedc", help='accestoken')
 
    # 解析命令行参数
    args = parser.parse_args()

      # 获取命令行参数的值
    file_path = args.file
    access_token = args.token
    
    ut=UploadTask("myuploadfile","",access_token, file_path)
    ut.begin_upload()
  
