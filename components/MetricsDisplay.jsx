import React from 'react';
import { Card, CardContent } from '@/components/ui/card';

const MetricsDisplay = ({ 
  faturamentoTotal, 
  valorEstoque, 
  totalSkus, 
  giroEstoque, 
  curvaA, 
  curvaB, 
  curvaC 
}) => {
  const mainMetrics = [
    {
      titulo: "Faturamento Total",
      valor: faturamentoTotal,
      className: "text-blue-600 dark:text-blue-400"
    },
    {
      titulo: "Valor Total em Estoque",
      valor: valorEstoque,
      className: "text-emerald-600 dark:text-emerald-400"
    },
    {
      titulo: "Total de SKUs",
      valor: totalSkus,
      className: "text-purple-600 dark:text-purple-400"
    }
  ];

  const distributionMetrics = [
    {
      titulo: "Giro de Estoque",
      valor: giroEstoque,
      className: "text-blue-600 dark:text-blue-400"
    },
    {
      titulo: "Curva A",
      valor: curvaA,
      className: "text-emerald-600 dark:text-emerald-400"
    },
    {
      titulo: "Curva B",
      valor: curvaB,
      className: "text-yellow-600 dark:text-yellow-400"
    },
    {
      titulo: "Curva C",
      valor: curvaC,
      className: "text-red-600 dark:text-red-400"
    }
  ];

  return (
    <div className="space-y-8">
      {/* Métricas Principais */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {mainMetrics.map((metric, index) => (
          <Card key={index} className="bg-white/90 dark:bg-gray-800/90 shadow-lg">
            <CardContent className="p-6">
              <div className="text-center">
                <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-2">
                  {metric.titulo}
                </h3>
                <p className={`text-2xl font-bold ${metric.className}`}>
                  {metric.valor}
                </p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Distribuição de SKUs */}
      <h2 className="text-xl font-semibold text-gray-800 dark:text-gray-200 mb-4">
        Distribuição de SKUs por Curva
      </h2>
      
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {distributionMetrics.map((metric, index) => (
          <Card key={index} className="bg-white/90 dark:bg-gray-800/90 shadow-lg">
            <CardContent className="p-6">
              <div className="text-center">
                <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-2">
                  {metric.titulo}
                </h3>
                <p className={`text-2xl font-bold ${metric.className}`}>
                  {metric.valor}
                </p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
};

export default MetricsDisplay;