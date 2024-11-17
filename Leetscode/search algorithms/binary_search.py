""" binary search will be applied on sorted arrays"""

"""Visualizer : https://binary-search-visualization.netlify.app/"""


def binary_search(arr, target):
    # Define the array and target value
    arr = sorted(arr)

    size = len(arr)
    start = 0
    end = size - 1
    # Loop until the start pointer crosses the end pointer
    while start <= end:
        # Calculate the middle index
        mid = (start + end) // 2

        if arr[mid] == target:
            return mid
        elif arr[mid] > target:
            end = mid - 1
        elif arr[mid] < target:
            start = mid + 1
    return -1


sorted_list = [10, 23, 33, 45, 50, 70, 85]
target = 50

result = binary_search(sorted_list, target)

print(result)
