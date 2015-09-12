import pickle
from flask import Flask, render_template, request
app = Flask(__name__)

@app.route('/')
@app.route('/leaderboards')
def display_leaderboards():
    # Unpickle leaderboard list
    lb_file_path = 'app_data/leaderboards.pkl'
    with open(lb_file_path, 'r') as f:
        leaderboards = pickle.load(f)

    return render_template('leaderboards.html', leaderboard=leaderboards[0])

if __name__ == '__main__':
    app.run(debug=True)
