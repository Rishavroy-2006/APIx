import React from 'react';

export const SkeletonBase = ({ className = "" }) => (
  <div className={`animate-pulse bg-gray-200 rounded-sm ${className}`} />
);

export const SkeletonText = ({ className = "h-4 w-1/3", lines = 1 }) => (
  <div className="space-y-2">
    {[...Array(lines)].map((_, i) => (
      <SkeletonBase key={i} className={`${className} ${i === lines - 1 && lines > 1 ? 'w-2/3' : 'w-full'}`} />
    ))}
  </div>
);

export const SkeletonCard = ({ height = "h-24" }) => (
  <div className={`border border-border bg-white p-4 flex flex-col gap-3 ${height}`}>
    <SkeletonBase className="h-3 w-1/2" />
    <SkeletonBase className="h-8 w-3/4 mt-auto" />
  </div>
);

export const SkeletonChart = ({ height = "h-72", title = true }) => (
  <div className="bg-white border border-border p-6 flex flex-col gap-4">
    {title && (
      <div>
        <SkeletonBase className="h-5 w-1/4 mb-2" />
        <SkeletonBase className="h-3 w-1/3" />
      </div>
    )}
    <SkeletonBase className={`w-full ${height}`} />
  </div>
);

export const SkeletonPage = () => (
  <div className="max-w-6xl mx-auto px-6 py-12 space-y-12 w-full">
    <div className="border border-border bg-white p-8 flex flex-col md:flex-row gap-6 justify-between">
      <div className="w-full max-w-md space-y-4">
        <SkeletonBase className="h-4 w-1/3" />
        <SkeletonBase className="h-16 w-3/4" />
        <SkeletonBase className="h-3 w-full" />
      </div>
    </div>
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      <SkeletonCard height="h-32" />
      <SkeletonCard height="h-32" />
      <SkeletonCard height="h-32" />
    </div>
    <SkeletonChart height="h-96" title={false} />
  </div>
);

export const SkeletonGovPortal = () => (
  <div className="max-w-7xl mx-auto px-6 py-8 space-y-8 w-full">
    <div className="border-b border-border pb-6 space-y-4">
      <SkeletonBase className="h-6 w-32" />
      <SkeletonBase className="h-10 w-2/3 md:w-1/3" />
      <SkeletonBase className="h-4 w-full md:w-1/2" />
    </div>
    <SkeletonChart height="h-72" />
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      {[...Array(6)].map((_, i) => <SkeletonCard key={i} height="h-28" />)}
    </div>
    <SkeletonChart height="h-64" />
    <SkeletonChart height="h-[28rem]" />
  </div>
);

export const SkeletonCitizenPortal = () => (
  <div className="max-w-6xl mx-auto px-6 py-8 space-y-8 w-full">
    <div className="border-b border-border pb-6 space-y-4">
      <SkeletonBase className="h-6 w-32" />
      <SkeletonBase className="h-10 w-2/3 md:w-1/3" />
      <SkeletonBase className="h-4 w-full md:w-1/2" />
    </div>
    <div className="flex flex-col md:flex-row gap-6">
      <SkeletonBase className="h-24 w-full md:w-2/3" />
      <SkeletonBase className="h-24 w-full md:w-1/3" />
    </div>
    <SkeletonChart height="h-64" />
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {[...Array(4)].map((_, i) => <SkeletonCard key={i} height="h-24" />)}
    </div>
  </div>
);

export const SkeletonLiveData = () => (
  <div className="max-w-7xl mx-auto px-6 py-8 space-y-8 w-full">
    <div className="border-b border-border pb-6 space-y-4">
      <SkeletonBase className="h-6 w-32" />
      <SkeletonBase className="h-10 w-2/3 md:w-1/3" />
      <SkeletonBase className="h-4 w-full md:w-1/2" />
    </div>
    <div className="flex gap-4 mb-4">
      <SkeletonBase className="h-10 w-40" />
      <SkeletonBase className="h-10 w-40" />
    </div>
    <SkeletonChart height="h-96" title={false} />
  </div>
);
