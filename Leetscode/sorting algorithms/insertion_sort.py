https://www.hackerearth.com/practice/algorithms/sorting/insertion-sort/visualize/

"""Visualizer : https://www.hackerearth.com/practice/algorithms/sorting/insertion-sort/visualize/"""


def insertion_sort(arr):
    n = len(arr)

    for i in range(n):
        min_index = i

        for j in range(min_index + 1, n):
            if arr[j] < arr[min_index]:
                min_index = j
        if i != min_index:
            arr[i], arr[min_index] = arr[min_index], arr[i]

    return arr

my_list = []

result = insertion_sort(my_list)

print(result)
