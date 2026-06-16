import multiprocessing
import os

NUM_PRODUCERS = 4

def run_producer():

    os.system(
        "python -m producer.producer"
    )

if __name__ == "__main__":

    processes = []

    for _ in range(NUM_PRODUCERS):

        p = multiprocessing.Process(
            target=run_producer
        )

        p.start()

        processes.append(p)

    for p in processes:
        p.join()