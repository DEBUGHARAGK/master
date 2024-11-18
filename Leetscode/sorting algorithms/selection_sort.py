"""Visualizer : https://www.hackerearth.com/practice/algorithms/sorting/selection-sort/visualize/"""


def selection_sort(arr):
    n = len(arr)

    for i in range(n):
        min_index = i

        for j in range(min_index + 1, n):
            if arr[j] < arr[min_index]:
                min_index = j
        if i != min_index:
            arr[i], arr[min_index] = arr[min_index], arr[i]

    return arr


# approach 2 :

# def selection_sort(arr):
#     n = len(arr)

#     for i in range(0, n - 1):
#         min_index = i

#         for j in range(i + 1, n):
#             if arr[j] < arr[min_index]:
#                 min_index = j
#         arr[i], arr[min_index] = arr[min_index], arr[i]

#     return arr


my_list = [12, 255, 11, 34, 90, 222, 2, 4]

result = selection_sort(my_list)

print(result)
