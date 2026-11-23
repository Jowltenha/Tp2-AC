-- Consulta de leitura usada pelo analista de dados
SELECT medico_id, dia, consultas
FROM vw_ocupacao_diaria
WHERE dia BETWEEN :inicio AND :fim
ORDER BY dia, medico_id;
