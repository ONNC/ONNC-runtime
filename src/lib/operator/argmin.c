#include <operator/argmin.h>

#include <stdint.h>
#include <stdbool.h>
#include <float.h>

static int32_t findIndex(index, axisDim, elementDistance){
    return (index / (axisDim * elementDistance)) * elementDistance + index % elementDistance;
}

void ONNC_RUNTIME_argmin_float(
  void * restrict onnc_runtime_context
  ,const float * restrict input_data
  ,int32_t input_data_ndim, const int32_t * restrict input_data_dims
  ,float * restrict output_reduced
  ,int32_t output_reduced_ndim, const int32_t * restrict output_reduced_dims
  ,int32_t axis
  ,int32_t keepdims
) {
    int32_t axisDim = input_data_dims[axis];

    int32_t axisElementDistance = 1;
    for(int32_t dim = axis + 1 ; dim < input_data_ndim ; dim++){
        axisElementDistance *= input_data_dims[dim];
    }

    int32_t size = axisElementDistance;
    for(int32_t dim = 0 ; dim <= axis ; dim++){
        size *= input_data_dims[dim];
    }

    int32_t try = 0;
    while(try < size){
        /* Initialize try context*/
        int32_t index = try;
        float min = FLT_MAX;
        int32_t axisIndex = 0, minIndex = 0;
        while(axisIndex < axisDim){
            if(input_data[index] < min){
                min = input_data[index];
                minIndex = axisIndex;
            }
            index += axisElementDistance;
            axisIndex += 1;
        }

        /* fill the data to output */
        int32_t fillIndex = findIndex(try, axisDim, axisElementDistance);
        output_reduced[fillIndex] = minIndex;

        /* update round context */
        if(try % axisElementDistance == axisElementDistance - 1){
             try = ((try + 1) - axisElementDistance) + axisElementDistance * axisDim;
         }
         else{
             try += 1;
         }
    }
}
