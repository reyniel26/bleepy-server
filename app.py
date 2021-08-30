from flask import Flask, render_template

app = Flask(__name__)

#Index Page
@app.route('/')
def index():
    #create template folder
    #inside of template folder is the home.html
    return render_template('home.html')

#Run APP
if __name__ == '__main__':
    app.secret_key = 'bleepy_server' #Set the secret_key
    app.run(debug=True)