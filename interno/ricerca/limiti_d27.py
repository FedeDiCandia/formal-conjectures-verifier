"""I limiti superiori noti per D(27,5,2), λ = 1, ricalcolati: 32 è davvero ammesso?"""
v, k, lam = 27, 5, 1
# Johnson–Schönheim per t = 2
U = (v * ((lam * (v - 1)) // (k - 1))) // k
print(f"Johnson–Schönheim: floor({v}/{k} * floor({lam}*{v-1}/{k-1})) = {U}")
# condizione di Hanani (abbassa di 1): lam(v-1) ≡ 0 mod (k-1) e lam v(v-1)/(k-1) ≡ -1 mod k
applicabile = (lam * (v - 1)) % (k - 1) == 0 and ((lam * v * (v - 1)) // (k - 1)) % k == k - 1
print(f"condizione di Hanani: lam(v-1) mod (k-1) = {(lam*(v-1))%(k-1)} -> "
      f"{'si applica, limite ' + str(U-1) if applicabile else 'non si applica'}")
# secondo limite di Johnson (t = 2): d(d-1) >= q(q-1)v + 2qr con kd = qv + r
for d in (31, 32, 33):
    q, r = divmod(k * d, v)
    lhs, rhs = d * (d - 1), q * (q - 1) * v + 2 * q * r
    print(f"secondo Johnson, d={d}: q={q} r={r}  d(d-1)={lhs} {'>=' if lhs>=rhs else '<'} {rhs}"
          f"  -> {'ammesso' if lhs >= rhs else 'ESCLUSO'}")
# conto dei gradi usato nella forma canonica
r_max = (v - 1) // (k - 1)
print(f"grado massimo di un punto: floor({v-1}/{k-1}) = {r_max}")
print(f"32 blocchi: somma dei gradi {32*k}, capienza {v*r_max}, deficienza {v*r_max-32*k}"
      f" -> almeno {v-(v*r_max-32*k)} punti di grado {r_max}")
