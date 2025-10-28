import math

# Ввод значений с клавиатуры
try:
    x = float(input("Введите значение x: "))
    y = float(input("Введите значение y: "))
    z = float(input("Введите значение z: "))

except ValueError:
    print("Ошибка: Введите числовые значения!")
    exit()

# Вычисление выражения M
# Проверка деления на ноль в знаменателе
if (x + 1 / (x**3 + 3)) == 0:
    print("Ошибка: Знаменатель выражения M равен нулю.")
else:
    numerator_M = math.exp(math.fabs(x - 1)) + y / (y**2 + 2)
    denominator_M = x + 1 / (x**3 + 3)
    M = (y - 3) * (numerator_M / denominator_M)
    print(f"Значение M = {M}")

# Вычисление выражения P
P = x * (math.atan(z) + math.exp(-((x / 2) + 3)))
print(f"Значение P = {P}")