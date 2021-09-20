# Bleepy Server
Bleepy  Server is the web version of python program can block tagalog and english profanity audio in videos.

## Includes
1. bleepy
2. Bleepy_UI
   - Bleepy_UI should be save in static folder

## Python modules needed
1. vosk-api
   - Offline speech recognition 
   - https://github.com/alphacep/vosk-api

2. alt-profanity-check
   - Profanity checker in string that uses machine learning
   - https://pypi.org/project/alt-profanity-check/
   - https://github.com/dimitrismistriotis/profanity-check

3. flask
4. flask-mysqldb
5. passlib