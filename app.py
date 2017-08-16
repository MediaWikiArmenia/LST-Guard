import lst_guard, lst_therapist
from multiprocessing import Process

def start_guard():
    lst_guard.run()

def start_therapist():
    lst_therapist.run()

if __name__ == '__main__':
    guard = Process(target=start_guard)
    guard.start()
    therapist = Process(target=start_therapist)
    therapist.start()
