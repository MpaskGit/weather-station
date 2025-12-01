FROM  python:3.9  


#update 
RUN apt-get update -y

#install packages
RUN apt-get install net-tools -y
RUN apt-get install vim -y

#Copy required files

COPY server_weather.py /

#sanity check
RUN touch server_weather.container

CMD ["python", "server_weather.py"]
