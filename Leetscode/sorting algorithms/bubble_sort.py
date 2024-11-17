"""Visualizer : https://www.hackerearth.com/practice/algorithms/sorting/bubble-sort/visualize/"""


def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        swapped = False
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
                swapped = True

        if not swapped:
            break
    return arr


if __name__ == "__main__":

    my_list = [12, 3, 4, 75, 99, 2, 8, 25, 105, 34]
    print(bubble_sort(my_list))
